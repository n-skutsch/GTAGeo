import argparse
import csv
import json
import os


def encode_locations(f, locations, setting, comma):
    """
    Encodes a list of locations in JSON format and writes them to the given file.

    Args:
        f (file handle): The file to which the encoded locations should be written.
        locations ([{}]): The locations that should be encoded.
        setting (string): The setting of the locations.
        comma (string): The character to add after all encoded locations.

    Returns:
        None
    """

    if len(locations) > 0:
        f.write('  "markers_{0}": [\n'.format(setting))
        for i, location in enumerate(locations):
            f.write('    [\n')
            f.write('      {0},\n'.format(location['x']))
            f.write('      {0}\n'.format(location['y']))
            if i == len(locations) - 1:
                f.write('    ]\n')
            else:
                f.write('    ],\n')
        f.write('  ]{0}\n'.format(comma))
    else:
        f.write('  "markers_{0}": []{1}\n'.format(setting, comma))


def convert_csv_to_json(input_file, output_file):
    """
    Converts a render targets file in CSV format to a markers file in JSON format.
    Removes the z-coordinate, rendered, and error.

    Args:
        input_file (string): The input file in CSV format.
        output_file (string): The output file in JSON format.

    Returns:
        None
    """

    # Create a list for each location setting
    urban = []
    rural = []
    drone = []

    # Open the input file
    with open(input_file, 'r') as f:

        # Read the data
        data = csv.DictReader(f, delimiter=';')

        # For each location, add it to the list of the corresponding setting
        for location in data:
            if location['setting'] == 'urban':
                urban.append(location)
            elif location['setting'] == 'rural':
                rural.append(location)
            elif location['setting'] == 'drone':
                drone.append(location)

    # Open the output file
    with open(output_file, 'w') as f:

        # Write the number of locations of each setting to the file
        f.write('{\n')
        f.write('  "count_urban": {0},\n'.format(len(urban)))
        f.write('  "count_rural": {0},\n'.format(len(rural)))
        f.write('  "count_drone": {0},\n'.format(len(drone)))

        # Write all locations of each setting to the file
        encode_locations(f, urban, 'urban', ',')
        encode_locations(f, rural, 'rural', ',')
        encode_locations(f, drone, 'drone', '')
        f.write('}\n')


def main():

    # Parse the input arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', '-i', help='Input file in CSV format', type=str, metavar='PATH',
                        default=os.path.join(os.getcwd(), 'render_targets.csv'))
    parser.add_argument('--output', '-o', help='Output file in JSON format', type=str, metavar='PATH',
                        default=os.path.join(os.getcwd(), 'gta_v_markers.json'))
    args = parser.parse_args()

    # Check if the input file exists
    print('[OS]        Checking the input file...')
    if not os.path.exists(args.input):
        print('[OS]        ERROR: The path "{0}" does not exist. Please check your files.'.format(args.input))
        print('[OS]        Usage: python translate_csv_to_json.py -i CSV_PATH')
        raise RuntimeError
    print('            Done.')

    # Convert the file
    print('[CSV]       Converting the list of markers from CSV to JSON format...')
    convert_csv_to_json(args.input, args.output)
    print('            Done.')


if __name__ == '__main__':
    main()