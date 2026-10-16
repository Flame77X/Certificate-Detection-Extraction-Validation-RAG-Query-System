"""
Rule-based field extraction: a free, offline stand-in for a key-value model
(e.g. Azure Document Intelligence). Reads labelled values such as
"Issued By: X" or "Valid Until: 2027-01-01" from OCR text.

Used when Azure OpenAI is not configured (or EXTRACTION_PROVIDER=rules).
Confidences are deliberately below the 0.80 flag threshold so results
are always marked for review.
"""
import re

# Explicit "Label: value" match
LABELLED_CONFIDENCE = 0.75
# Subject inferred from certificate phrasing ("has completed the ...")
HEURISTIC_CONFIDENCE = 0.6

_MONTHS = r'(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
DATE = (
    r'(\d{4}-\d{2}-\d{2}'
    r'|\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4}'
    rf'|{_MONTHS}\.?\s+\d{{1,2}},?\s+\d{{4}}'
    rf'|\d{{1,2}}\s+{_MONTHS}\.?,?\s+\d{{4}})'
)
SEP = r'\s*[:\-#.]?\s*'

PATTERNS = {
    # Stop at sentence punctuation or " on <date>" so prose like "issued by X on 5 May 2024." works
    'issuer': rf'(?:issued\s+by|issuer|awarded\s+by|certifying\s+(?:body|authority)){SEP}(?P<v>[^\n.;,]+?)(?=\s+on\s|[.;,]\s|[.;,]?$|\n)',
    'certificate_number': (
        r'(?:certificate\s*(?:no\.?|number|id)|credential\s*id|cert\.?\s*(?:no\.?|#)|'
        r'reg(?:istration)?\.?\s*(?:no\.?|number)|ref(?:erence)?\.?\s*(?:no\.?|number)|'
        r'serial\s*(?:no\.?|number)|validation\s*number)'
        rf'{SEP}(?P<v>[A-Z0-9][A-Z0-9\-/.()]{{3,}})'
    ),
    # Letters usually carry a plain "Date: ..." line
    'issued_date': rf'(?:date\s+of\s+issue|issued\s+on|issue\s+date|date\s+issued|awarded\s+on|\bdated?\s*:){SEP}(?P<v>{DATE})',
    'expiry_date': rf'(?:valid\s+until|valid\s+till|valid\s+thr(?:u|ough)|expiry\s+date|expiration\s+date|expires(?:\s+on)?){SEP}(?P<v>{DATE})',
    # Explicit colon required: "completed the course" must not match as a label
    'subject': r'(?:^|\n)[ \t]*(?:subject|course|program(?:me)?|qualification)[ \t]*:[ \t]*(?P<v>[^\n]+)',
}

# Lines like "has successfully completed the" are usually followed by the subject
SUBJECT_LEADS = re.compile(
    r'(?:has\s+(?:successfully\s+)?completed(?:\s+the)?(?:\s+course)?|is\s+hereby\s+awarded(?:\s+the)?|'
    r'in\s+recognition\s+of\s+completing(?:\s+the)?|for\s+completing(?:\s+the)?)\s*:?\s*$',
    re.IGNORECASE,
)

# Prose subject: "thesis titled X under the guidance ..." (run on whitespace-joined text)
SUBJECT_TITLED = re.compile(
    r'(?:thesis|dissertation|project|course|program(?:me)?|training|internship)\s+(?:titled|entitled)\s+'
    r'["“]?(?P<v>[^"”]+?)["”]?(?=\s+(?:under|at|from|with|during|on\s+\d)\b|[.;]|$)',
    re.IGNORECASE,
)

# Letterhead fallback for issuer: first organisation-like line near the top of the page
ORG_WORDS = re.compile(
    r'\b(?:institute|university|college|academy|school|board|council|ministry|department|foundation|'
    r'corporation|company|ltd|limited|inc|llc|pvt|association|society|authority|organi[sz]ation)\b',
    re.IGNORECASE,
)
LETTERHEAD_LINES = 8

def _clean(value):
    value = re.sub(r'\s+', ' ', value).strip(' .,:;-')
    return value or None

def _subject_from_phrasing(lines):
    for i, line in enumerate(lines[:-1]):
        if SUBJECT_LEADS.search(line.strip()):
            nxt = lines[i + 1].strip()
            if nxt:
                return nxt
    return None

def _issuer_from_letterhead(lines):
    for line in lines[:LETTERHEAD_LINES]:
        line = line.strip()
        if 5 <= len(line) <= 80 and ORG_WORDS.search(line) and not line.startswith('(') and ':' not in line:
            return line
    return None

def extract_with_rules(text_content):
    """
    Return {field: {'value', 'confidence'}} for the 5 target fields, plus '_method': 'rules'.
    Absent fields are None with LABELLED_CONFIDENCE (the rules consistently found nothing).
    """
    text = text_content or ''
    result = {}
    for field, pattern in PATTERNS.items():
        match = re.search(pattern, text, re.IGNORECASE)
        value = _clean(match.group('v')) if match else None
        result[field] = {'value': value, 'confidence': LABELLED_CONFIDENCE}

    lines = [l for l in text.splitlines() if l.strip()]

    if result['subject']['value'] is None:
        subject = _subject_from_phrasing(lines)
        if not subject:
            match = SUBJECT_TITLED.search(' '.join(text.split()))
            subject = match.group('v') if match else None
        if subject:
            result['subject'] = {'value': _clean(subject), 'confidence': HEURISTIC_CONFIDENCE}

    if result['issuer']['value'] is None:
        issuer = _issuer_from_letterhead(lines)
        if issuer:
            result['issuer'] = {'value': _clean(issuer), 'confidence': HEURISTIC_CONFIDENCE}

    result['_method'] = 'rules'
    return result
