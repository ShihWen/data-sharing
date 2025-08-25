SCHEDULE_INTERVALS = {
    'weekly': '0 2 * * 6',      # Saturday 10 AM Taiwan time
    'daily': '0 2 * * *',       # Daily 10 AM Taiwan time
    'hourly': '0 * * * *',      # Every hour
    'manual': None               # Manual trigger only
}

DAG_TAGS = {
    'mrt': ['mrt', 'transport', 'taipei'],
    'osm': ['osm', 'road-network', 'geospatial'],
    'reference': ['reference', 'boundaries', 'dimensions']
}