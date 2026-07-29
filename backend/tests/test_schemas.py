import unittest

from pydantic import ValidationError

from app.schemas import CompanyCreate


class TestCompanySchemas(unittest.TestCase):
    def test_company_name_is_normalized(self) -> None:
        company = CompanyCreate(name="  Ola   Electric  ")
        self.assertEqual(company.name, "Ola Electric")

    def test_short_company_name_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            CompanyCreate(name="A")


if __name__ == "__main__":
    unittest.main()

