'''
This module contains global variables used across the server application.
'''
import os

simulation_mode = os.environ.get('SIMULATION_MODE', True) != False

mitre_faiss_db = None