from bulk_data_manipulation.common import parse_natural_boolean_string, NoNaturalBooleanValueFound
from django.test import SimpleTestCase


class HelperFunctionsTests(SimpleTestCase):
    def test_natural_boolean(self):
        self.assertEqual(parse_natural_boolean_string('True'), True)
        self.assertEqual(parse_natural_boolean_string('TRUE'), True)
        self.assertEqual(parse_natural_boolean_string(True), True)
        self.assertEqual(parse_natural_boolean_string('checked'), True)
        self.assertEqual(parse_natural_boolean_string('1'), True)
        self.assertEqual(parse_natural_boolean_string(''), None)
        self.assertEqual(parse_natural_boolean_string('None'), None)
        self.assertEqual(parse_natural_boolean_string(None), None)
        self.assertEqual(parse_natural_boolean_string('False'), False)
        self.assertEqual(parse_natural_boolean_string('FALSE'), False)
        self.assertEqual(parse_natural_boolean_string(False), False)
        self.assertEqual(parse_natural_boolean_string('0'), False)
        self.assertEqual(parse_natural_boolean_string('unchecked'), False)
        self.assertRaises(NoNaturalBooleanValueFound, parse_natural_boolean_string, 'Verily verily!')
