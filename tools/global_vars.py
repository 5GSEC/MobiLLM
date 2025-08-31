'''
This module contains global variables used across the server application.
'''
import os

simulation_mode = os.environ.get('SIMULATION_MODE', True) != 'false'

mitre_faiss_db = None