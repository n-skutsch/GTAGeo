import argparse
import csv
import json
import os


def convert_json_to_csv(input_file, output_file):
    """
    Converts a markers file in JSON format to a render targets file in CSV format.
    Sets the z-coordinate to 0.0, rendered to False, and error to False.

    Args:
        input_file (string): The input file in JSON format.
        output_file (string): The output file in CSV format.

    Returns:
        None
    """

    # Open the input file and read the data
    with open(input_file, 'r') as f:
        data = json.load(f)

    # Open the output file
    with open(output_file, 'w', newline='') as f:

        # Define the header and write it to the file
        fieldnames = ['setting', 'x', 'y', 'z', 'rendered']
        csv_writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
        csv_writer.writeheader()

        # Write all locations in urban setting to the file
        for marker in data['markers_urban']:
            csv_writer.writerow({'setting': 'urban', 'x': marker[0], 'y': marker[1], 'z': 0,
                'rendered': False})

        # Write all locations in rural setting to the file
        for marker in data['markers_rural']:
            csv_writer.writerow({'setting': 'rural', 'x': marker[0], 'y': marker[1], 'z': 0,
                'rendered': False})

        # Write all locations in drone setting to the file
        for marker in data['markers_drone']:
            csv_writer.writerow({'setting': 'drone', 'x': marker[0], 'y': marker[1], 'z': 0,
                'rendered': False})


def main():

    # Parse the input arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', '-i', help='Input file in JSON format', type=str, metavar='PATH',
                        default=os.path.join(os.getcwd(), 'gta_v_markers.json'))
    parser.add_argument('--output', '-o', help='Output file in CSV format', type=str, metavar='PATH',
                        default=os.path.join(os.getcwd(), 'render_targets.csv'))
    args = parser.parse_args()

    # Check if the input file exists
    print('[OS]        Checking the input file...')
    if not os.path.exists(args.input):
        print('[OS]        ERROR: The path "{0}" does not exist. Please check your files.'.format(args.input))
        print('[OS]        Usage: python translate_json_to_csv.py -i JSON_PATH')
        raise RuntimeError
    print('            Done.')

    # Convert the file
    print('[CSV]       Converting the list of markers from JSON to CSV format...')
    convert_json_to_csv(args.input, args.output)
    print('            Done.')


if __name__ == '__main__':
    main()