##########################################################################
## Summary
##########################################################################

'''
Python scripts are used to pre-process existing data sources into formats that we need to call from the on-page javascript.
'''


##########################################################################
## Imports & Configuration
##########################################################################
import logging
import json
import pandas as pd
from sqlalchemy import create_engine
import csv
import dateutil

#Configure logging. See /logs/example-logging.py for examples of how to use this.
logging_filename = "../logs/ingestion.log"
logging.basicConfig(filename=logging_filename, level=logging.DEBUG)
logging.warning("--------------------starting module------------------")
#Pushes everything from the logger to the command line output as well.
logging.getLogger().addHandler(logging.StreamHandler())

#############################
#CONSTANTS
#############################
constants = {
    'secrets_filename': 'secrets.json',
    'manifest_filename': 'load_manifest.csv',
    'date_headers_filename': 'load_date_headers.json',
}

def get_connect_str():
    "Loads the secrets json file to retrieve the connection string"
    logging.info("Loading secrets from {}".format(constants['secrets_filename']))
    with open(constants['secrets_filename']) as fh:
        secrets = json.load(fh)
    return secrets['database']['connect_str']

def get_column_names(path):

    with open(path) as f:
        myreader=csv.reader(f,delimiter=',')
        headers = next(myreader)
    return headers

def csv_to_sql(index_path):
    # Get the list of files to load - using Pandas dataframe (df), although we don't need most of the functionality that Pandas provides.
    paths_df = pd.read_csv(index_path, parse_dates=['date'])
    logging.info("Preparing to load " + str(len(paths_df.index)) + " files")

    # Connect to SQL - uses sqlalchemy so that we can write from pandas dataframe.
    connect_str = get_connect_str()
    engine = create_engine(connect_str)

    for index, row in paths_df.iterrows():
        if (row['skip'] == "skip") or (row['skip'] == "loaded") or (row['skip'] == "invalid"):
            logging.info("Row " + row['table_name'] + ": " + row['skip'])
        else:
            full_path = row['path'] + row['filename']
            tablename = row['table_name']

            logging.info("loading table " + str(index + 1) + " (" + tablename + ")")

            #Since different files have different date columns, we need to compare to the master list.
            headers = list(get_column_names(full_path))
            with open(constants['date_headers_filename']) as fh:
                date_headers = json.load(fh)
                parseable_headers = date_headers['date_headers']
            to_parse = list(set(parseable_headers) & set(headers))
            logging.info("  identified date columns: " + str(to_parse))

            #Custom date parser required to handle null dates. Currently only allows one date format though.
                #PresCat is m/d/yyyy
                #Integreated_Tax is yyyy-mm-ddThh:mm:ss.000Z
                #removed: format='%m/%d/%Y'
            parser = lambda x: pd.to_datetime(x, errors='coerce', infer_datetime_format=True)

            #Read the file into Pandas, and then reformat the column names to follow SQL conventions/best practice.
            csv_df = pd.read_csv(full_path, encoding="latin_1", parse_dates=to_parse, date_parser=parser)
            csv_df.columns = map(str.lower, csv_df.columns)
            csv_df.columns = [c.replace(' ', '_') for c in csv_df.columns]
            csv_df.columns = [c.replace('.', '_') for c in csv_df.columns]
            logging.info("  in memory...")

            #Add a column so that we can put all the snapshots in the same table
            csv_df['data_version'] = row['data_version']

            #Send to the database
            csv_df.to_sql(tablename, engine, if_exists='append')
            logging.info("  table loaded")

if __name__ == '__main__':
    #sample_add_to_database()
    csv_to_sql(constants['manifest_filename'])
