import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def process_data(data):
    """Processes numerical data to calculate the average."""
    try:
        # Check if the input is a list
        if not isinstance(data, list):
            raise TypeError("Input data must be a list.")

        # Check if the list contains only numbers
        if not all(isinstance(item, (int, float)) for item in data):
            raise ValueError("List must contain only numbers.")

        # Calculate the average
        average = sum(data) / len(data)
        logging.info(f"Calculated average: {average}")
        return average

    except TypeError as e:
        logging.error(f"TypeError: {e}")
        return None
    except ValueError as e:
        logging.error(f"ValueError: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return None