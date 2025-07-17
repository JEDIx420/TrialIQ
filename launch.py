import subprocess
import os

# CML provides the application port in the 'CDSW_APP_PORT' or 'PORT' environment variable.
# We fetch it here. Default to 8501 if not found, for local testing.
port = os.environ.get("CDSW_APP_PORT") or os.environ.get("PORT", "8501")

# We use 0.0.0.0 to allow the CML proxy to connect to the Streamlit app.
# The command is constructed as a single string to be run with shell=True.
command = f"streamlit run trialiq.py --server.port {port} --server.address 0.0.0.0 --server.enableCORS false --theme.base dark"

print(f"Executing: {command}")

# Run the Streamlit application using the constructed command.
# The output of the subprocess will be streamed to the console.
subprocess.run(command, shell=True)
