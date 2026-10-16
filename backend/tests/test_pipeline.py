import unittest
from unittest import mock
from types import SimpleNamespace
import importlib.util
import io
import os
import shutil
import sys
import tempfile

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(BACKEND_DIR)

from app import field_extraction as fe
from app import rag_pipeline as rp
from app import ocr_module
from app import llm_client
from app import external_verification as ev
from app.rule_extraction import extract_with_rules
from app.date_validation import validate_dates, validate_issuer, normalize_issuer
from app.logging_utils import check_for_issues
from app.security import validate_secure_path, redact_pii, ALLOWED_DATA_DIR
from app.status_assignment import assign_certificate_status


def fake_chat_client(contents):
    """Client whose chat.completions.create returns the given contents in order."""
    replies = iter(contents)
    def create(**_kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=next(replies)))])
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


class TestChatBackendSelection(unittest.TestCase):
    AZURE = {'AZURE_OPENAI_API_KEY': 'k', 'AZURE_OPENAI_ENDPOINT': 'https://x.openai.azure.com'}
    HF = {'HF_TOKEN': 'hf_abc123'}

    OPENROUTER = {'OPENROUTER_API_KEY': 'sk-or-v1-abc'}

    def backend(self, env):
        clean = {k: '' for k in ('AZURE_OPENAI_API_KEY', 'AZURE_OPENAI_ENDPOINT', 'HF_TOKEN', 'LLM_PROVIDER', 'HF_MODEL',
                                 'OPENROUTER_API_KEY', 'OPENROUTER_MODEL', 'LLM_API_KEY', 'LLM_BASE_URL', 'LLM_MODEL')}
        with mock.patch.dict(os.environ, {**clean, **env}):
            return llm_client.get_chat_backend()

    def test_azure_preferred_when_both_configured(self):
        self.assertEqual(self.backend({**self.AZURE, **self.HF}).provider, 'azure')

    def test_huggingface_when_only_token(self):
        backend = self.backend(self.HF)
        self.assertEqual((backend.provider, backend.model), ('huggingface', llm_client.HF_DEFAULT_MODEL))
        self.assertEqual(str(backend.client.base_url).rstrip('/'), llm_client.HF_BASE_URL)

    def test_forced_provider_and_model_override(self):
        backend = self.backend({**self.AZURE, **self.HF, 'LLM_PROVIDER': 'huggingface', 'HF_MODEL': 'org/model'})
        self.assertEqual((backend.provider, backend.model), ('huggingface', 'org/model'))

    def test_openrouter_free_model_preferred_over_huggingface(self):
        backend = self.backend({**self.OPENROUTER, **self.HF})
        self.assertEqual((backend.provider, backend.model), ('openrouter', llm_client.OPENROUTER_DEFAULT_MODEL))
        self.assertEqual(str(backend.client.base_url).rstrip('/'), llm_client.OPENROUTER_BASE_URL)

    def test_custom_openai_compatible_needs_url_and_model(self):
        self.assertIsNone(self.backend({'LLM_API_KEY': 'k', 'LLM_BASE_URL': 'https://api.example.com/v1'}))
        backend = self.backend({'LLM_API_KEY': 'k', 'LLM_BASE_URL': 'https://api.example.com/v1', 'LLM_MODEL': 'llama'})
        self.assertEqual((backend.provider, backend.model), ('custom', 'llama'))

    def test_none_without_credentials_or_with_placeholders(self):
        self.assertIsNone(self.backend({}))
        self.assertIsNone(self.backend({'HF_TOKEN': 'hf_your_token_here'}))


class TestOCRRouting(unittest.TestCase):

    def route(self, provider, configured, vision_text='azure text'):
        with mock.patch.dict(os.environ, {'OCR_PROVIDER': provider}), \
             mock.patch.object(ocr_module, 'is_configured', return_value=configured), \
             mock.patch.object(ocr_module, '_vision_ocr', return_value=vision_text) as vision, \
             mock.patch.object(ocr_module, '_local_ocr', return_value='local text') as local:
            return ocr_module.ocr_image(b'img', 'image/png'), vision.called, local.called

    def test_auto_without_azure_uses_local(self):
        self.assertEqual(self.route('auto', False), ('local text', False, True))

    def test_auto_with_azure_uses_vision(self):
        self.assertEqual(self.route('auto', True), ('azure text', True, False))

    def test_auto_falls_back_to_local_when_vision_empty(self):
        self.assertEqual(self.route('auto', True, vision_text=''), ('local text', True, True))

    def test_forced_local(self):
        self.assertEqual(self.route('local', True), ('local text', False, True))

    @unittest.skipUnless(importlib.util.find_spec('rapidocr'), 'rapidocr not installed')
    def test_local_ocr_reads_synthetic_samples(self):
        with mock.patch.dict(os.environ, {'OCR_PROVIDER': 'local'}):
            for name in ('sample_cert_image.png', 'sample_scanned_cert.pdf'):
                text, used_ocr = ocr_module.extract_text_from_file(os.path.join(ALLOWED_DATA_DIR, name))
                self.assertTrue(used_ocr, name)
                self.assertIn('Certificate Number', text, name)


class TestConsensus(unittest.TestCase):

    def test_confidence_is_agreement_ratio(self):
        runs = [{'issuer': 'A'}, {'issuer': 'B'}, {'issuer': 'B'}]
        result, log = fe.calculate_consensus(runs)
        self.assertEqual(result['issuer'], {'value': 'B', 'confidence': 0.67})
        self.assertEqual(log['issuer']['total_runs'], 3)

    def test_votes_ignore_case_and_whitespace(self):
        runs = [{'issuer': 'AWS Training'}, {'issuer': 'aws  training'}, {'issuer': 'AWS Training'}]
        result, _ = fe.calculate_consensus(runs)
        self.assertEqual(result['issuer'], {'value': 'AWS Training', 'confidence': 1.0})

    def test_agreed_absence_keeps_confidence(self):
        runs = [{'expiry_date': None}, {'expiry_date': None}, {'expiry_date': '2030-01-01'}]
        result, _ = fe.calculate_consensus(runs)
        self.assertEqual(result['expiry_date'], {'value': None, 'confidence': 0.67})

    def test_failed_runs_lower_confidence(self):
        result, _ = fe.calculate_consensus([{'issuer': 'A'}], total_runs=3)
        self.assertEqual(result['issuer']['confidence'], 0.33)


class TestExtraction(unittest.TestCase):

    def test_parse_json_tolerates_fences(self):
        self.assertEqual(fe._parse_json_object('```json\n{"a": 1}\n```'), {'a': 1})
        with self.assertRaises(ValueError):
            fe._parse_json_object('no json here')

    def test_extract_single_normalises_values(self):
        client = fake_chat_client(['{"issuer": " IEEE ", "certificate_number": 12345, "subject": ""}'])
        result = fe._extract_single('text', llm_client.ChatBackend(client, 'm', 'huggingface'))
        self.assertEqual(result['issuer'], 'IEEE')
        self.assertEqual(result['certificate_number'], '12345')
        self.assertIsNone(result['subject'])
        self.assertIsNone(result['expiry_date'])

    def test_extract_single_returns_none_on_bad_output(self):
        backend = llm_client.ChatBackend(fake_chat_client(['not json']), 'm', 'huggingface')
        self.assertIsNone(fe._extract_single('text', backend))

    def test_huggingface_consensus(self):
        reply = '{"issuer": "IEEE", "certificate_number": "IE-1", "issued_date": "2024-01-01", "subject": "X"}'
        backend = llm_client.ChatBackend(fake_chat_client([reply] * 3), 'Qwen/test', 'huggingface')
        with mock.patch.object(fe, 'get_chat_backend', return_value=backend), \
             mock.patch.dict(os.environ, {'EXTRACTION_PROVIDER': 'auto'}):
            out = fe.extract_with_azure('text')
        self.assertEqual(out['_method'], 'huggingface_consensus')
        self.assertEqual(out['issuer'], {'value': 'IEEE', 'confidence': 1.0})

    def test_all_llm_runs_failing_falls_back_to_rules(self):
        backend = llm_client.ChatBackend(fake_chat_client(['not json'] * 3), 'Qwen/test', 'huggingface')
        with mock.patch.object(fe, 'get_chat_backend', return_value=backend), \
             mock.patch.dict(os.environ, {'EXTRACTION_PROVIDER': 'auto'}):
            out = fe.extract_with_azure('Issued By: IEEE')
        self.assertEqual(out['_method'], 'rules')
        self.assertEqual(out['issuer']['value'], 'IEEE')

    def test_no_client_without_mock_uses_rules(self):
        with mock.patch.object(fe, 'get_chat_backend', return_value=None), \
             mock.patch.dict(os.environ, {'USE_MOCK_LLM': '0', 'EXTRACTION_PROVIDER': 'auto'}):
            out = fe.extract_with_azure('Issued By: IEEE\nCertificate Number: IE-2024-001')
        self.assertEqual(out['_method'], 'rules')
        self.assertEqual(out['issuer']['value'], 'IEEE')

    def test_forced_rules_skips_llm(self):
        with mock.patch.object(fe, 'get_chat_backend') as get_chat_backend, \
             mock.patch.dict(os.environ, {'EXTRACTION_PROVIDER': 'rules'}):
            self.assertEqual(fe.extract_with_azure('text')['_method'], 'rules')
        get_chat_backend.assert_not_called()

    def test_mock_mode_is_opt_in(self):
        with mock.patch.object(fe, 'get_chat_backend', return_value=None), \
             mock.patch.dict(os.environ, {'USE_MOCK_LLM': '1'}):
            fields, confidence = fe.extract_fields(fe.extract_with_azure('text'))
        self.assertEqual(fields['issuer'], 'ISO Authority')
        self.assertEqual(fields['issued_date'], '2024-01-15')
        self.assertEqual(confidence['issuer'], 1.0)


class TestNoExpiryCertificates(unittest.TestCase):

    def test_missing_expiry_is_not_an_error(self):
        res = validate_dates('2024-01-01', None)
        self.assertEqual(res['expiry_status'], 'no_expiry')
        self.assertTrue(res['issued_date_valid'])
        self.assertTrue(res['dates_consistent'])

    def test_missing_issued_date_is_still_invalid(self):
        self.assertFalse(validate_dates(None, '2030-01-01')['issued_date_valid'])

    def test_no_missing_flag_for_optional_expiry(self):
        flags = check_for_issues({'issuer': 'IEEE', 'expiry_date': None}, {'issuer': 1.0, 'expiry_date': 1.0})
        self.assertEqual(flags, [])

    def test_no_expiry_certificate_can_be_verified(self):
        fields = {'issuer': 'IEEE', 'issued_date': '2024-01-01', 'subject': 'X', 'expiry_date': None}
        data = {'fields': fields, 'confidence': {k: 1.0 for k in fields}}
        status = assign_certificate_status(data, validate_dates('2024-01-01', None), {'is_trusted': True})
        self.assertEqual(status, 'Verified')


class TestRuleExtraction(unittest.TestCase):

    def values(self, text):
        return {k: v['value'] for k, v in extract_with_rules(text).items() if k != '_method'}

    def test_labelled_certificate(self):
        text = open(os.path.join(ALLOWED_DATA_DIR, 'sample_certificate.txt'), encoding='utf-8').read()
        self.assertEqual(self.values(text), {
            'issuer': 'Global Tech Institute', 'certificate_number': 'GTI-2024-88A',
            'issued_date': '2024-03-10', 'expiry_date': '2027-03-10',
            'subject': 'Advanced Python Systems Engineering'})

    def test_prose_and_alternative_labels(self):
        vals = self.values('This certificate is issued by IEEE on 5 March 2024. Credential ID: AB12-99.\n'
                           'Expires on March 5, 2027')
        self.assertEqual(vals['issuer'], 'IEEE')
        self.assertEqual(vals['certificate_number'], 'AB12-99')
        self.assertEqual(vals['expiry_date'], 'March 5, 2027')

    def test_letter_format(self):
        # Fictional institution: letterhead issuer, Ref.No., "Date:" line, "thesis titled ..." subject
        text = ('NIT\nNorthfield Institute of Technology\n(Established under the Northfield Act)\n'
                'Office of Research\nRef.No.:NIT/R(AR)/2024/L07\nDate: December 20, 2025\n'
                'TO WHOMSOEVER IT MAY CONCERN\nThis is to certify that Ms. Jane Sample has submitted her\n'
                'thesis titled Robust Solar Panel Coatings for\nHumid Climates under the guidance of Dr. Example.')
        self.assertEqual(self.values(text), {
            'issuer': 'Northfield Institute of Technology', 'certificate_number': 'NIT/R(AR)/2024/L07',
            'issued_date': 'December 20, 2025', 'expiry_date': None,
            'subject': 'Robust Solar Panel Coatings for Humid Climates'})

    def test_confidence_stays_below_flag_threshold(self):
        out = extract_with_rules('Issued By: IEEE')
        self.assertTrue(all(v['confidence'] < 0.8 for k, v in out.items() if k != '_method'))


class FakeResponse:
    def __init__(self, status=200, payload=None, location=None):
        import json
        self.status_code = status
        self.headers = {'Location': location} if location else {}
        self.is_redirect = location is not None
        self.raw = io.BytesIO(json.dumps(payload).encode() if payload is not None else b'<html></html>')
        self.raw.read = lambda n, decode_content=True, _r=self.raw.read: _r(n)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestExternalVerification(unittest.TestCase):
    BADGE_ID = '0b5c1c3e-1111-2222-3333-444455556666'
    TEXT = f'Verify: https://www.credly.com/badges/{BADGE_ID}/public_url'

    def assertion(self, **overrides):
        data = {'type': 'Assertion', 'badge': 'https://api.credly.com/v1/obi/v2/badge_classes/b1'}
        data.update(overrides)
        return data

    def verify(self, responses, issuer='Global Tech Institute', text=None):
        """responses: {url: FakeResponse}; any other URL fails the test."""
        def fake_get(url, **_kwargs):
            if url not in responses:
                raise AssertionError(f'unexpected fetch {url}')
            return responses[url]
        with mock.patch.object(ev.requests, 'get', side_effect=fake_get):
            return ev.verify_external_issuer(issuer, {}, text or self.TEXT)

    def responses(self, assertion, issuer_name='Global Tech Institute'):
        return {
            ev.CREDLY_ASSERTION_API.format(self.BADGE_ID): FakeResponse(payload={'data': assertion}),
            'https://api.credly.com/v1/obi/v2/badge_classes/b1': FakeResponse(
                payload={'name': 'ML Foundations', 'issuer': {'name': issuer_name}}),
        }

    def test_url_allowlist_blocks_ssrf_targets(self):
        text = ('https://169.254.169.254/latest http://localhost/x https://credly.com.evil.io/a '
                f'http://www.credly.com/badges/{self.BADGE_ID}')
        self.assertEqual(ev.find_verification_urls(text), [f'https://www.credly.com/badges/{self.BADGE_ID}'])

    def test_active_badge_is_verified(self):
        result = self.verify(self.responses(self.assertion()))
        self.assertEqual(result['status'], 'Verified (Open Badges)')

    def test_revoked_badge_fails(self):
        result = self.verify(self.responses(self.assertion(revoked=True)))
        self.assertEqual(result['status'], 'Failed (Revoked)')

    def test_expired_badge_fails(self):
        result = self.verify(self.responses(self.assertion(expires='2020-01-01T00:00:00Z')))
        self.assertEqual(result['status'], 'Failed (Expired)')

    def test_issuer_mismatch_fails(self):
        result = self.verify(self.responses(self.assertion(), issuer_name='Someone Else Academy'))
        self.assertEqual(result['status'], 'Failed (Issuer mismatch)')

    def test_redirect_off_allowlist_is_not_followed(self):
        responses = {ev.CREDLY_ASSERTION_API.format(self.BADGE_ID):
                     FakeResponse(status=302, location='https://attacker.example/x')}
        self.assertIn('Manual', self.verify(responses)['status'])

    def test_no_url_requires_manual_review(self):
        self.assertIn('Manual', self.verify({}, text='no links here')['status'])


class TestStatusAssignment(unittest.TestCase):
    FIELDS = {'issuer': 'IEEE', 'issued_date': '2024-01-01', 'subject': 'X'}
    TRUSTED = {'is_trusted': True}
    VALID = {'expiry_status': 'valid', 'issued_date_valid': True}

    def status(self, fields=None, conf=0.9, issuer=None, validation=None):
        data = {'fields': fields or self.FIELDS, 'confidence': {'issuer': conf}}
        return assign_certificate_status(data, validation or self.VALID, issuer or self.TRUSTED)

    def test_branches_in_priority_order(self):
        self.assertEqual(self.status(), 'Verified')
        self.assertEqual(self.status(conf=0.5), 'Manual Review Required')
        self.assertEqual(self.status(issuer={'is_trusted': False}), 'Untrusted Issuer')
        self.assertEqual(self.status(validation={'expiry_status': 'expired'}), 'Expired')
        self.assertEqual(self.status(fields={'issuer': 'IEEE'}), 'Manual Review Required')
        self.assertEqual(self.status(validation={'expiry_status': 'valid', 'issued_date_valid': False}),
                         'Verification Failed')


class TestIssuerMatching(unittest.TestCase):

    def test_normalisation(self):
        self.assertEqual(normalize_issuer('PramAnA AyurTech Solutions Pvt. Ltd.'), 'pramana ayurtech solutions')

    def test_trusted_variants(self):
        for name in ['AWS Training', 'aws training.', 'Oracle University Ltd', 'Microsft Training']:
            self.assertTrue(validate_issuer(name)['is_trusted'], name)

    def test_untrusted(self):
        for name in ['Microsoft', 'AWS', 'Fake University', None, '']:
            self.assertFalse(validate_issuer(name)['is_trusted'], name)


class TestSecurity(unittest.TestCase):

    def test_path_traversal_rejected(self):
        with self.assertRaises(PermissionError):
            validate_secure_path(os.path.join(ALLOWED_DATA_DIR, '..', 'app.py'))

    def test_path_inside_data_accepted(self):
        path = os.path.join(ALLOWED_DATA_DIR, 'sample_certificate.txt')
        self.assertEqual(validate_secure_path(path), os.path.abspath(path))

    def test_redact_pii(self):
        redacted = redact_pii({'certificate_number': 'ABC123', 'issuer': 'IEEE'})
        self.assertEqual(redacted['certificate_number'], 'AB***REDACTED***')
        self.assertEqual(redacted['issuer'], 'IEEE')


class TestRAG(unittest.TestCase):

    def setUp(self):
        self.db_dir = tempfile.mkdtemp()
        # No chat model unless a test provides one (ignores any real HF_TOKEN / Azure env)
        patcher = mock.patch.object(rp, 'get_chat_backend', return_value=None)
        self.get_chat_backend = patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def local_embed(_self, text):
        text = text.lower()
        return [1.0 if 'cloud' in text else 0.05, 1.0 if 'learning' in text else 0.05, 0.1]

    def offline_rag_with_chat(self, chat_client):
        """Local embeddings (no Azure) + Hugging Face chat backend."""
        self.get_chat_backend.return_value = llm_client.ChatBackend(chat_client, 'Qwen/test', 'huggingface')
        with mock.patch.object(rp, 'get_client', return_value=None), \
             mock.patch.object(rp.CertificateRAG, '_local_embed', self.local_embed):
            rag = rp.CertificateRAG(db_path=self.db_dir)
            rag.ingest_certificate({'doc_id': 'C1', 'final_status': 'Verified',
                                    'fields': {'issuer': 'Ministry of Education', 'subject': 'Cloud Operations'}})
            return rag, rag.answer_question('Which cloud certificate do I have?')

    def test_huggingface_generates_answer_over_local_search(self):
        rag, result = self.offline_rag_with_chat(fake_chat_client(['You have Cloud Operations [C1]']))
        self.assertEqual(rag.collection.name, 'certificates_local')
        self.assertEqual(result['answer'], 'You have Cloud Operations [C1]')
        self.assertEqual(result['sources'][0]['doc_id'], 'C1')

    def test_huggingface_failure_falls_back_to_records(self):
        def create(**_kwargs):
            err = RuntimeError('Payment required')
            err.status_code = 402
            raise err
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        _, result = self.offline_rag_with_chat(client)
        self.assertIn('huggingface model is unavailable right now (HTTP 402)', result['answer'])
        self.assertIn('Issuer: Ministry of Education', result['answer'])

    def tearDown(self):
        shutil.rmtree(self.db_dir, ignore_errors=True)

    def test_list_certificates_newest_first(self):
        with mock.patch.object(rp, 'get_client', return_value=None), \
             mock.patch.object(rp.CertificateRAG, '_local_embed', self.local_embed):
            rag = rp.CertificateRAG(db_path=self.db_dir)
            rag.ingest_certificate({'doc_id': 'OLD', 'fields': {'issuer': 'A'}})
            rag.ingest_certificate({'doc_id': 'NEW', 'fields': {'issuer': 'B'}})
            items = rag.list_certificates()
        self.assertEqual([i['doc_id'] for i in items], ['NEW', 'OLD'])
        self.assertEqual(items[0]['issuer'], 'B')

    def test_forced_azure_without_client_indexes_nothing(self):
        with mock.patch.object(rp, 'get_client', return_value=None), \
             mock.patch.dict(os.environ, {'RAG_EMBEDDINGS': 'azure'}):
            rag = rp.CertificateRAG(db_path=self.db_dir)
            result = rag.ingest_certificate({'doc_id': 'C1', 'fields': {}})
            self.assertFalse(result['success'])
            self.assertEqual(rag.collection.count(), 0)
            self.assertEqual(rag.answer_question('anything')['sources'], [])

    def test_offline_mode_returns_closest_records(self):
        def fake_local_embed(_self, text):
            text = text.lower()
            return [1.0 if 'cloud' in text else 0.05, 1.0 if 'learning' in text else 0.05, 0.1]
        with mock.patch.object(rp, 'get_client', return_value=None), \
             mock.patch.dict(os.environ, {'RAG_EMBEDDINGS': 'auto'}), \
             mock.patch.object(rp.CertificateRAG, '_local_embed', fake_local_embed):
            rag = rp.CertificateRAG(db_path=self.db_dir)
            self.assertEqual(rag.collection.name, 'certificates_local')
            rag.ingest_certificate({'doc_id': 'C1', 'final_status': 'Verified',
                                    'fields': {'issuer': 'Ministry of Education', 'subject': 'Cloud Operations'}})
            rag.ingest_certificate({'doc_id': 'C2', 'fields': {'issuer': 'IEEE', 'subject': 'Machine Learning'}})
            result = rag.answer_question('Which cloud certificate do I have?')
        self.assertEqual([s['doc_id'] for s in result['sources']], ['C1'])
        self.assertIn('Issuer: Ministry of Education', result['answer'])

        # Question about the open document returns that record even when wording doesn't match it
        with mock.patch.object(rp, 'get_client', return_value=None), \
             mock.patch.object(rp.CertificateRAG, '_local_embed', fake_local_embed):
            rag = rp.CertificateRAG(db_path=self.db_dir)
            result = rag.answer_question('What is this certificate?', doc_id='C2')
        self.assertEqual([s['doc_id'] for s in result['sources']], ['C2'])
        self.assertIn('Subject: Machine Learning', result['answer'])

    def test_answer_includes_sources(self):
        def embed(**kwargs):
            text = kwargs['input'].lower()
            return SimpleNamespace(data=[SimpleNamespace(embedding=[1.0 if 'iso' in text else 0.01, 0.5])])
        client = fake_chat_client(['Expires 2026-01-15 [C2]'])
        client.embeddings = SimpleNamespace(create=embed)
        self.get_chat_backend.return_value = llm_client.ChatBackend(client, 'gpt-4o', 'azure')
        with mock.patch.object(rp, 'get_client', return_value=client):
            rag = rp.CertificateRAG(db_path=self.db_dir)
            rag.ingest_certificate({'doc_id': 'C1', 'fields': {'issuer': 'AWS Training'}})
            rag.ingest_certificate({'doc_id': 'C2', 'fields': {'issuer': 'ISO Authority'}})
            result = rag.answer_question('When does the ISO certificate expire?')
        self.assertEqual(result['answer'], 'Expires 2026-01-15 [C2]')
        self.assertEqual(result['sources'][0]['doc_id'], 'C2')


class TestFlaskAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # backend/app.py is shadowed by the backend/app/ package, so load it by path
        spec = importlib.util.spec_from_file_location('server', os.path.join(BACKEND_DIR, 'app.py'))
        cls.server = importlib.util.module_from_spec(spec)
        with mock.patch('app.rag_pipeline.CertificateRAG'):
            spec.loader.exec_module(cls.server)
        cls.client = cls.server.app.test_client()

    def setUp(self):
        self.upload_dir = tempfile.mkdtemp()
        self.server.UPLOAD_FOLDER = self.upload_dir
        self.server.rag = mock.Mock()

    def tearDown(self):
        shutil.rmtree(self.upload_dir, ignore_errors=True)

    def upload(self, filename, content=b'data'):
        return self.client.post('/upload', data={'file': (io.BytesIO(content), filename)},
                                content_type='multipart/form-data')

    def test_rejects_disallowed_extension(self):
        res = self.upload('evil.py')
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json['success'])

    def test_traversal_filename_is_sanitised(self):
        with mock.patch.object(self.server, 'process_single_file', return_value={'doc_id': 'x'}) as proc:
            res = self.upload('../../cert.txt')
        self.assertEqual(res.status_code, 200)
        saved_path = proc.call_args[0][0]
        self.assertEqual(saved_path, os.path.join(self.upload_dir, 'cert.txt'))
        self.server.rag.ingest_certificate.assert_called_once_with({'doc_id': 'x'})

    def test_not_a_certificate_returns_400(self):
        with mock.patch.object(self.server, 'process_single_file', return_value=None):
            self.assertEqual(self.upload('cert.txt').status_code, 400)

    def test_oversized_upload_returns_413(self):
        too_big = b'0' * (self.server.MAX_FILE_SIZE_MB * 1024 * 1024 + 1)
        self.assertEqual(self.upload('big.pdf', too_big).status_code, 413)

    def test_history_lists_indexed_certificates(self):
        self.server.rag.list_certificates.return_value = [{'doc_id': 'C1', 'issuer': 'IEEE', 'status': 'Verified'}]
        res = self.client.get('/history')
        self.assertEqual(res.json, {'items': [{'doc_id': 'C1', 'issuer': 'IEEE', 'status': 'Verified'}]})

    def test_settings_reports_config_without_secrets(self):
        self.server.rag.embedding_mode = 'local'
        self.server.rag.collection.count.return_value = 2
        env = {'HF_TOKEN': 'hf_secretvalue123', 'AZURE_OPENAI_API_KEY': '', 'LLM_PROVIDER': ''}
        with mock.patch.dict(os.environ, env):
            res = self.client.get('/settings')
        self.assertEqual(res.json['llm']['provider'], 'huggingface')
        self.assertEqual(res.json['indexed_certificates'], 2)
        self.assertIn('IEEE', res.json['trusted_issuers'])
        self.assertNotIn('hf_secretvalue123', res.get_data(as_text=True))

    def test_query_requires_question(self):
        self.assertEqual(self.client.post('/query', json={}).status_code, 400)

    def test_query_returns_answer_and_sources(self):
        self.server.rag.answer_question.return_value = {'answer': 'A', 'sources': [{'doc_id': 'C1'}]}
        res = self.client.post('/query', json={'question': 'who issued C1?', 'doc_id': 'C1'})
        self.assertEqual(res.json, {'answer': 'A', 'sources': [{'doc_id': 'C1'}]})
        self.server.rag.answer_question.assert_called_with('who issued C1?', doc_id='C1')


if __name__ == '__main__':
    unittest.main()
