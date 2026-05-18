import app
instances, infos = app.load_scrapers(enabled_names=['linkedin', 'naukri', 'indeed', 'unstop', 'shine'])
print(f"Instances: {instances}")
