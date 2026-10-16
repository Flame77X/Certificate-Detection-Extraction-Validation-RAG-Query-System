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


class TestOCRRouting(unittest.TestCase):

    def route(self, provider, configured, vision_text='azure text'):
        with mock.patch.dict(os.environ, {'OCR_PROVIDER': provider}),              mock.patch.object(ocr_module, 'is_configured', return_value=configured),              mock.patch.object(ocr_module, '_vision_ocr', return_value=vision_text) as vision,              mock.patch.object(ocr_module, '_local_ocr', return_value='local text') as local:
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
        result = fe._extract_single('text', client)
        self.assertEqual(result['issuer'], 'IEEE')
        self.assertEqual(result['certificate_number'], '12345')
        self.assertIsNone(result['subject'])
        self.assertIsNone(result['expiry_date'])

    def test_extract_single_returns_none_on_bad_output(self):
        self.assertIsNone(fe._extract_single('text', fake_chat_client(['not json'])))

    def test_no_client_without_mock_returns_empty(self):
        with mock.patch.object(fe, 'get_client', return_value=None), \
             mock.patch.dict(os.environ, {'USE_MOCK_LLM': '0'}):
            self.assertEqual(fe.extract_with_azure('text'), {})

    def test_mock_mode_is_opt_in(self):
        with mock.patch.object(fe, 'get_client', return_value=None), \
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

    def tearDown(self):
        shutil.rmtree(self.db_dir, ignore_errors=True)

    def test_without_client_nothing_is_indexed(self):
        with mock.patch.object(rp, 'get_client', return_value=None):
            rag = rp.CertificateRAG(db_path=self.db_dir)
            result = rag.ingest_certificate({'doc_id': 'C1', 'fields': {}})
            self.assertFalse(result['success'])
            self.assertEqual(rag.collection.count(), 0)
            self.assertEqual(rag.answer_question('anything')['sources'], [])

    def test_answer_includes_sources(self):
        def embed(**kwargs):
            text = kwargs['input'].lower()
            return SimpleNamespace(data=[SimpleNamespace(embedding=[1.0 if 'iso' in text else 0.01, 0.5])])
        client = fake_chat_client(['Expires 2026-01-15 [C2]'])
        client.embeddings = SimpleNamespace(create=embed)
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

    def test_query_requires_question(self):
        self.assertEqual(self.client.post('/query', json={}).status_code, 400)

    def test_query_returns_answer_and_sources(self):
        self.server.rag.answer_question.return_value = {'answer': 'A', 'sources': [{'doc_id': 'C1'}]}
        res = self.client.post('/query', json={'question': 'who issued C1?'})
        self.assertEqual(res.json, {'answer': 'A', 'sources': [{'doc_id': 'C1'}]})


if __name__ == '__main__':
    unittest.main()
