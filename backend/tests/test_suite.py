import unittest
from datetime import datetime # Fix path to import modules from parent directory
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.certificate_identification import is_certificate
from app.date_validation import validate_dates
from app.field_extraction import normalize_date
from app.logging_utils import check_for_issues

class TestCertificateSystem(unittest.TestCase):

    def test_certificate_identification(self):
        """Test identification logic"""
        # Valid case
        self.assertTrue(is_certificate('pdf', 'This certificate is issued by ISO and valid until 2025'))
        # Invalid file type
        self.assertFalse(is_certificate('exe', 'certificate issued by'))
        # Not enough keywords
        self.assertFalse(is_certificate('pdf', 'This is just a random document'))
    
    def test_date_validation(self):
        """Test date validation logic"""
        # Valid dates
        res = validate_dates('2024-01-01', '2030-01-01')
        self.assertTrue(res['issued_date_valid'])
        self.assertEqual(res['expiry_status'], 'valid')
        
        # Expired
        res = validate_dates('2020-01-01', '2021-01-01') # Assuming running in 2026 or later, this is expired
        # If running in 2026 (local time is 2026-01-10), this is definitely expired
        self.assertEqual(res['expiry_status'], 'expired')
        
        # Inconsistent (Issued AFTER Expiry)
        res = validate_dates('2026-01-01', '2025-01-01')
        self.assertFalse(res['dates_consistent'])

        # Future Issued Date
        # Assuming current date is 2026-01-10
        res = validate_dates('2099-01-01', '2100-01-01')
        self.assertFalse(res['issued_date_valid'])

    def test_date_normalization(self):
        """Test date format normalization"""
        self.assertEqual(normalize_date('15/01/2024'), '2024-01-15')
        self.assertEqual(normalize_date('January 15, 2024'), '2024-01-15')
        self.assertEqual(normalize_date('2024-01-15'), '2024-01-15')
        # Invalid format should return original
        self.assertEqual(normalize_date('NotADate'), 'NotADate')

    def test_issue_checking(self):
        """Test flag generation for low quality data"""
        fields = {'a': 'b'}
        
        # Good confidence
        conf_good = {'a': 0.99}
        self.assertEqual(check_for_issues(fields, conf_good), [])
        
        # Low confidence
        conf_bad = {'a': 0.50}
        flags = check_for_issues(fields, conf_bad)
        self.assertIn('LOW_CONFIDENCE_A', flags)
        
        # Missing field
        fields_missing = {'a': ''}
        flags = check_for_issues(fields_missing, conf_good)
        self.assertIn('MISSING_A', flags)

if __name__ == '__main__':
    print("Running comprehensive system tests...")
    unittest.main()
