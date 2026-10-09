#!/usr/bin/env python3
"""
Initialize and verify the SQLite database for Apex Logistics Claim Engine.
"""
from seed_data import seed_database

def init_database():
    seed_database()

if __name__ == "__main__":
    init_database()
