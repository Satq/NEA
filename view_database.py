#!/usr/bin/env python3
"""
Database Viewer for Smart Budgeting System
Quick script to view database contents (no external dependencies)
"""

import sqlite3
import sys
import os


def view_database(db_path="smart_budgeting_system.db"):
    """View all tables and their contents"""
    if not os.path.exists(db_path):
        print(f"Error: Database file '{db_path}' not found.")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # This allows column access by name
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()
        
        if not tables:
            print("No tables found in database.")
            return
        
        print("=" * 80)
        print("SMART BUDGETING SYSTEM DATABASE VIEWER")
        print("=" * 80)
        print(f"\nDatabase: {db_path}\n")
        
        for table in tables:
            table_name = table[0]
            if table_name == 'sqlite_sequence':
                continue  # Skip SQLite internal table
            
            print(f"\n{'=' * 80}")
            print(f"TABLE: {table_name.upper()}")
            print(f"{'=' * 80}")
            
            # Get table schema
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            # Get all data
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            
            if rows:
                # Print column headers
                print(f"\nColumns: {', '.join(column_names)}")
                print(f"Rows: {len(rows)}\n")
                print("-" * 80)
                
                # Print each row
                for i, row in enumerate(rows, 1):
                    print(f"Row {i}:")
                    for col_name in column_names:
                        value = row[col_name]
                        # Mask password hashes for security
                        if 'password' in col_name.lower() or 'salt' in col_name.lower():
                            value = "***HIDDEN***" if value else None
                        print(f"  {col_name}: {value}")
                    print()
            else:
                print("\n(No data in this table)")
            
            print()
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")


def view_table(db_path="smart_budgeting_system.db", table_name=None):
    """View a specific table"""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if table_name:
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            
            # Get column names
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            print(f"\n{table_name.upper()} Table")
            print("=" * 80)
            print(f"Columns: {', '.join(column_names)}")
            print(f"Rows: {len(rows)}\n")
            
            if rows:
                for i, row in enumerate(rows, 1):
                    print(f"Row {i}:")
                    for col_name in column_names:
                        value = row[col_name]
                        if 'password' in col_name.lower() or 'salt' in col_name.lower():
                            value = "***HIDDEN***" if value else None
                        print(f"  {col_name}: {value}")
                    print()
            else:
                print("(No data)")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "smart_budgeting_system.db"
    table_name = sys.argv[2] if len(sys.argv) > 2 else None
    
    if table_name:
        view_table(db_path, table_name)
    else:
        view_database(db_path)
