from hilife_scraper import crawler_cnvnts_hilife # Import the scraper class
import logging

logging.basicConfig(
    level=logging.INFO,  # Set the minimum level of messages to log
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def hilife_scraper_entrypoint(request):
    """
    Cloud Function entry point to trigger the Hilife scraper.
    The 'request' argument is required for Cloud Functions, even if not used.
    """
    logging.info("Starting Hilife scraper Cloud Function...")
    scraper = None
    try:
        scraper = crawler_cnvnts_hilife() # Initialize the scraper
        scraper.gotohilife() # Run the scraping logic
        scraper.upload_to_bigquery() # Upload results to BigQuery
        logging.info("Hilife scraper completed successfully. Data should be in BigQuery.")
        return "Hilife scraper executed successfully!"
    except Exception as e:
        logging.error(f"An error occurred during Cloud Function execution: {e}", exc_info=True)
        return f"Error during Hilife scraper execution: {e}", 500
    finally:
        if scraper:
            scraper.teardown() # Close the browser instance
