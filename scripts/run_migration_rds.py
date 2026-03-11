#!/usr/bin/env python3
"""
Run Alembic migration on RDS.
Tries multiple methods to get database connection:
1. DATABASE_URL environment variable (if it's RDS, not local 'db')
2. AWS Secrets Manager (RDS_SECRET_NAME)
3. SSM Parameter Store (/airex/rds/database-url)
"""

import os
import sys
import subprocess
import json

def get_from_ssm_parameter(parameter_name: str, region: str = "us-east-1"):
    """Get value from SSM Parameter Store."""
    try:
        import boto3
        client = boto3.client("ssm", region_name=region)
        response = client.get_parameter(Name=parameter_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except Exception as e:
        return None

def get_database_url_from_secret(secret_name: str, region: str = "us-east-1"):
    """Get database URL from AWS Secrets Manager.
    Handles both JSON format and direct connection string format.
    """
    try:
        import boto3
        from botocore.exceptions import ClientError
        
        client = boto3.client("secretsmanager", region_name=region)
        response = client.get_secret_value(SecretId=secret_name)
        secret_value = response["SecretString"]
        
        # Try to parse as JSON first
        try:
            secret = json.loads(secret_value)
            # If it's a dict, extract connection components
            if isinstance(secret, dict):
                username = secret.get("username") or secret.get("user")
                password = secret.get("password")
                host = secret.get("host") or secret.get("endpoint")
                port = secret.get("port", "5432")
                dbname = secret.get("dbname") or secret.get("database") or secret.get("db")
                
                if not all([username, password, host, dbname]):
                    raise ValueError("Secret missing required fields")
                
                return f"postgresql://{username}:{password}@{host}:{port}/{dbname}"
            else:
                # If JSON but not a dict, treat as string
                secret_value = str(secret)
        except (json.JSONDecodeError, ValueError):
            # Not JSON, treat as direct connection string
            pass
        
        # If it's already a connection string, use it directly
        if secret_value.startswith(("postgresql://", "postgres://", "postgresql+asyncpg://")):
            # Keep original format - env.py will handle it
            return secret_value
        
        # If it's just a string but not a connection string, it might be the URL
        # Try to use it as-is
        return secret_value
        
    except ImportError:
        print("Error: boto3 not installed. Install with: pip install boto3")
        return None
    except ClientError as e:
        print(f"Error retrieving secret '{secret_name}': {e}")
        return None
    except Exception as e:
        print(f"Error processing secret: {e}")
        return None

def main():
    database_url = None
    region = os.getenv("AWS_REGION", "ap-south-1")
    
    # Method 1: Check DATABASE_URL (but skip if it's local Docker 'db')
    env_db_url = os.getenv("DATABASE_URL", "")
    if env_db_url and "db:5432" not in env_db_url and "@db/" not in env_db_url:
        database_url = env_db_url  # Keep original format
        print("Using DATABASE_URL from environment")
    
    # Method 2: Try Secrets Manager
    if not database_url:
        secret_name = os.getenv("RDS_SECRET_NAME", "")
        if secret_name:
            print(f"Fetching from Secrets Manager: {secret_name}")
            database_url = get_database_url_from_secret(secret_name, region)
            if database_url:
                print("✓ Retrieved from Secrets Manager")
    
    # Method 3: Try common secret names
    if not database_url:
        common_secrets = [
            "/airex/prod/backend/database_url",  # Full connection string
            "airex/prod/backend/database_url",

            "airex/rds/database",
            "airex/database/rds", 
            "rds/airex/database",
            "airex-rds-database",
        ]
        for secret_name in common_secrets:
            print(f"Trying secret: {secret_name}")
            database_url = get_database_url_from_secret(secret_name, region)
            if database_url:
                print(f"✓ Found secret: {secret_name}")
                break
    
    # Method 4: Try SSM Parameter Store
    if not database_url:
        ssm_params = [
            "/airex/rds/database-url",
            "/airex/database/url",
            "/rds/database-url",
        ]
        for param_name in ssm_params:
            print(f"Trying SSM parameter: {param_name}")
            database_url = get_from_ssm_parameter(param_name, region)
            if database_url:
                print(f"✓ Found in SSM: {param_name}")
                break
    
    if not database_url:
        print("\n✗ Could not find RDS connection information")
        print("\nPlease provide one of:")
        print("  1. DATABASE_URL environment variable (RDS connection string)")
        print("  2. RDS_SECRET_NAME environment variable (Secrets Manager secret name)")
        print("\nExample:")
        print("  RDS_SECRET_NAME=airex/rds/database python3 scripts/run_migration_rds.py")
        sys.exit(1)
    
    # Mask password for display
    if "@" in database_url:
        masked = database_url.split("@")[0].split(":")[0] + ":***@" + database_url.split("@")[1]
        print(f"\nDatabase: {masked}")
    
    # Set environment for Alembic
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    
    # Set PYTHONPATH so airex_core can be imported
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    airex_core_path = os.path.join(project_root, 'services', 'airex-core')
    pythonpath = env.get('PYTHONPATH', '')
    if pythonpath:
        env['PYTHONPATH'] = f"{airex_core_path}:{pythonpath}"
    else:
        env['PYTHONPATH'] = airex_core_path
    
    print("\nRunning Alembic migration...")
    try:
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd="database",
            env=env,
            check=True
        )
        print("\n✓ Migration completed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Migration failed: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("\n✗ Alembic not found. Install with: pip install alembic")
        sys.exit(1)

if __name__ == "__main__":
    main()
