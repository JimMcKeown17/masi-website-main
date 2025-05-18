import json

with open('school_data.json', 'r') as f:
    data = json.load(f)

for item in data:
    if item['model'] == 'dashboards.school':
        item['model'] = 'api.school'

with open('updated_school_data.json', 'w') as f:
    json.dump(data, f, indent=2)