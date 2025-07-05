import sys
import json
import google.generativeai as genai
import re
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Set the backend to Agg before importing pyplot
import matplotlib.pyplot as plt
import numpy as np
import base64
from io import BytesIO
import os
import mariadb
from dotenv import load_dotenv
load_dotenv()



gemini_api_key = os.getenv("API_KEY")


config = {
    'host': os.getenv("DATABASE_HOST"),
    'user': os.getenv("DATABASE_USER"),
    'password': os.getenv("DATABASE_PASSWORD"),  # Replace with your actual password
    'database': os.getenv("DATABASE_NAME")         # Replace with your actual database name
}

conn = mariadb.connect(
            user=config['user'],
            password=config['password'],
            host=config['host'],
            port=3307,
            database=config['database']
        )
cur = conn.cursor()


# Function to extract SQL from Gemini's response
def extract_sql(output):
    sql_match = re.search(r"```sql(.*?)```", output, re.DOTALL)
    if sql_match:
        sql_code = sql_match.group(1).strip()
        return " ".join(sql_code.split())  # Convert to single-line SQL
    return ""

########### MariaDB Connection and Query Execution ###########
def extract_data(lst):
    """Extracts a string value from the SQL result set."""
    if lst and isinstance(lst[0], tuple) and len(lst[0]) == 1:
        return str(lst[0][0])
    return None

def execute_query(cursor, query):
    """Executes an SQL query and returns the extracted result."""
    try:
        cursor.execute(query)
        result = cursor.fetchall()
        return result
    except mariadb.Error as e:
        print(f"SQL Execution Error: {e}")
        return None
##############################################################



extract_context = ""
file_path = os.path.join('prompts', 'prompt1_extract.txt')
with open(file_path, 'r', encoding='utf-8') as file:
    extract_context = file.read()

base_context = ""
file_path = os.path.join('prompts', 'prompt2_sql.txt')
with open(file_path, 'r', encoding='utf-8') as file:
    base_context = file.read()


# Function to generate SQL using Gemini
def generate_sql(question):
    # Configure the API (you should use environment variables in production)
    genai.configure(api_key=gemini_api_key)  # Replace with your actual key
    model = genai.GenerativeModel("gemini-2.0-flash")

    question_context = extract_context + question
    response = model.generate_content(question_context)
    sql_extract_response = extract_sql(response.text)

    name_context = execute_query(cur, sql_extract_response)

    
    question_context = base_context + question + str(name_context)
    response = model.generate_content(question_context)
    sql_response = extract_sql(response.text)
    
    return sql_response

# Function to generate visualization code
def generate_visualization(question, data):
    try:
        print("Starting visualization generation...")
        print(f"Question: {question}")
        print(f"Data type: {type(data)}")
        
        # Configure the API
        genai.configure(api_key=gemini_api_key)
        
        # Initialize the model
        model = genai.GenerativeModel("gemini-2.0-flash")
        
        # Convert data to a DataFrame
        if isinstance(data, dict) and 'headers' in data and 'rows' in data:
            df = pd.DataFrame(data['rows'], columns=data['headers'])
        else:
            df = pd.DataFrame(data)
        
        print(f"Created DataFrame with shape: {df.shape}")
        print(f"DataFrame columns: {df.columns.tolist()}")
        print(f"First few rows:\n{df.head()}")
        
        # Create data description
        data_description = f"Data columns: {', '.join(df.columns.tolist())}\n"
        data_description += f"Number of rows: {len(df)}\n"
        #data_description += "First few rows:\n"
        data_description += "Data rows:\n"
        #data_description += df.head(3).to_string()
        data_description += df[:].to_string()
        
        # Define the prompt for visualization
        viz_prompt = f'''
        I have the following data from a SQL query about Premier League soccer:
        
        {data_description}
        
        The query was asking: "{question}"

        Here are some different options of graphs to choose from: Bar Chart, Line Graph, Scatterplot, Box & Whisker Plot, Pie Chart, Stacked Area Graph.
        
        Choose the best one, then please generate Python code using matplotlib that creates an appropriate visualization for this data.
        The code should:
        1. Create a clear and professional visualization
        2. Set appropriate titles, labels, and annotations
        3. Use a pleasant color scheme
        4. Handle any potential data type issues
        5. Include proper error handling
        
        IMPORTANT: The code should create a visualization using the provided data. Create a df from this data. Do not include plt.close() in the code.
        The code must save the plot to 'static/visualization.png' using plt.savefig('static/visualization.png').
        Do not include any import statements or function definitions.
        Just write the code that creates and saves the plot.
        '''
        
        print("Generating visualization code...")
        response = model.generate_content(viz_prompt)
        viz_code = response.text
        print(f"Generated code:\n{viz_code}")
        
        # Extract the code from the response
        code_match = re.search(r"```python(.*?)```", viz_code, re.DOTALL)
        if code_match:
            viz_code = code_match.group(1).strip()
            print("Extracted visualization code")
            print(f"Code to execute:\n{viz_code}")
            
            # Create a new figure
            plt.figure(figsize=(10, 6))
            
            try:
                print("Executing visualization code...")
                # Execute the visualization code with all necessary imports
                exec(viz_code, {
                    'df': df,
                    'plt': plt,
                    'np': np,
                    'pd': pd  # Add pandas to the execution context
                })
                
                # Get the absolute path to the static directory
                static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
                if not os.path.exists(static_dir):
                    os.makedirs(static_dir)
                
                # Save the plot with absolute path
                output_path = os.path.join(static_dir, 'visualization.png')
                print(f"Saving plot to: {output_path}")
                
                # Ensure the directory exists and is writable
                if not os.access(static_dir, os.W_OK):
                    raise PermissionError(f"Cannot write to directory: {static_dir}")
                
                # Save the plot with high DPI and proper format
                plt.savefig(output_path, 
                          bbox_inches='tight', 
                          dpi=300,
                          format='png',
                          facecolor='white')
                plt.close()
                print("Plot saved successfully")
                
                # Set proper file permissions
                try:
                    os.chmod(output_path, 0o644)  # Readable by all, writable by owner
                except Exception as e:
                    print(f"Warning: Could not set file permissions: {e}")
                
                # Verify the file was created and has content
                if os.path.exists(output_path):
                    file_size = os.path.getsize(output_path)
                    print(f"File exists with size: {file_size} bytes")
                    if file_size > 0:
                        print("File has content")
                        return True
                    else:
                        print("File is empty")
                        return False
                else:
                    print("File was not created")
                    return False
                
            except Exception as e:
                print(f"Error executing visualization code: {str(e)}")
                print(f"Error type: {type(e)}")
                import traceback
                print(f"Traceback: {traceback.format_exc()}")
                plt.close()
                return False
            
        print("No code found in response")
        return False
            
    except Exception as e:
        print(f"Error generating visualization: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False

def main():
    if len(sys.argv) < 3:
        print("Usage: python gemini_api.py [operation] [query] [data_json]")
        sys.exit(1)
    
    operation = sys.argv[1]  # 'sql' or 'viz'
    query = sys.argv[2]      # The natural language query
    
    if operation == 'sql':
        # Generate SQL query
        sql_query = generate_sql(query)
        print(sql_query)  # Output to stdout for Node.js to capture
    
    elif operation == 'viz':
        if len(sys.argv) < 4:
            print("Error: Data JSON required for visualization")
            sys.exit(1)
        
        data_json = sys.argv[3]  # JSON string of data
        data = json.loads(data_json)
        
        # Generate visualization code
        viz_code = generate_visualization(query, data)
        print(viz_code)  # Output to stdout for Node.js to capture
    
    else:
        print(f"Error: Unknown operation '{operation}'")
        sys.exit(1)

if __name__ == "__main__":
    main()