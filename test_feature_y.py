import unittest
from feature_y import process_data

class TestFeatureY(unittest.TestCase):

    def test_process_data_valid_input(self):
        data = [1, 2, 3, 4, 5]
        processed_data = process_data(data)
        self.assertEqual(processed_data, 3.0)

    def test_process_data_invalid_input_type(self):
        data = "invalid"
        processed_data = process_data(data)
        self.assertIsNone(processed_data)

    def test_process_data_invalid_input_value(self):
        data = [1, 2, "a", 4, 5]
        processed_data = process_data(data)
        self.assertIsNone(processed_data)

if __name__ == '__main__':
    unittest.main()