import json
import os
import csv

JOB_TYPE = "rbs"
SAMPLE_TYPE = "rbs_random"
PHI = 15
ZETA = ""
DET = 0.15
THETA = 170
RUN_NUMBER = 11 # TODO: Wat is dit?

parent_dir = os.path.dirname(os.path.abspath(__file__))
example_json_path = os.path.join(parent_dir, "example.json")
output_csv_path = None
example_json = None

try:
    with open(example_json_path) as r:
        example_json = json.load(r)

    request_name = example_json['request_name']
    sample_list = example_json['samples']
    
    output_csv_path = os.path.join(parent_dir, f"{request_name}.csv")

    with open(output_csv_path, 'w', newline='') as csv_file:
        writer = csv.writer(csv_file)

        writer.writerow(['name', 'job_type'] + [''] * 8)
        writer.writerow([request_name, JOB_TYPE] + [''] * 8)

        writer.writerow([''] * 10)

        writer.writerow(['type', 'sample_name', 'charge_total', 'x', 'y', 'phi', 'zeta', 'det', 'theta'])

        for sample in sample_list:
            charge_total = f"{request_name}_{sample['file']}"
            
            row = [
                SAMPLE_TYPE,
                sample['sample_id'],
                charge_total,
                sample['x'],
                sample['y'],
                PHI,
                ZETA,
                DET,
                THETA,
                RUN_NUMBER
            ]
            writer.writerow(row)
            
    print(f"Successfully generated CSV file at: {output_csv_path}")

except FileNotFoundError:
    print(f"Error: The file was not found at {example_json_path}")
except KeyError as e:
    print(f"Error: The JSON file is missing a required key: {e}")
except json.JSONDecodeError:
    print(f"Error: The file at {example_json_path} is not a valid JSON file.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")