import tablib
from django.test import TestCase
from .narwhal import BooleanWidgetValidated, resource_model_mapping
from core.models import Person


class NarwhalTestCase(TestCase):

    def test_booleanwidgetvalidated(self):
        with self.subTest(value='INVALID'):
            with self.assertRaises(ValueError):
                BooleanWidgetValidated().clean(value='INVALID')
        with self.subTest(value='CHECKED'):
            self.assertTrue(
                BooleanWidgetValidated().clean(value='TRUE'),
                msg='Unexpected validation error for "TRUE"'
            )
        with self.subTest(value='FALSE'):
            self.assertFalse(
                BooleanWidgetValidated().clean(value='FALSE'),
                msg='Unexpected validation error for "FALSE"'
            )
        with self.subTest(value=''):
            self.assertIsNone(
                BooleanWidgetValidated().clean(value=''),
                msg='Unexpected validation error for blank value'
            )

    def test_resources(self):
        ResourceClass = resource_model_mapping['Person']
        resource = ResourceClass()
        dataset = tablib.Dataset(['person quasicontinuous'], headers=['name'])
        result = resource.import_data(dataset, dry_run=False)
        self.assertEqual(
            1,
            Person.objects.all().count()
        )
        self.assertEqual(Person.objects.last().name,
            'person quasicontinuous'
        )
