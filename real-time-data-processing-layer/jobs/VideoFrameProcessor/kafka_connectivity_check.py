from environment import KAFKA_BOOTSTRAP_SERVERS
import subprocess
from logger import logger

# This function performs a connectivity check with a Kafka cluster.
# It begins by installing the 'kafkacat' tool if it's not already present on the system.
# It then executes a query to obtain information about the Kafka cluster specified in the environment variables and logs the results.
# In case of an error, the function handles exceptions and logs any errors.
# @Author: Sergio Sánchez Sánchez
def kafka_connectivity_check():
    try:
        # Update the package list and install 'kafkacat'
        subprocess.check_call(["apt-get", "update"])
        subprocess.check_call(["apt-get", "install", "kafkacat", "-y"])
        logger.info("kafkacat has been successfully installed.")
        
        # Check Kafka connectivity and retrieve cluster information
        command = ["kafkacat", "-L", "-b", KAFKA_BOOTSTRAP_SERVERS]
        output = subprocess.check_output(command, stderr=subprocess.STDOUT, universal_newlines=True)
        logger.info("Kafka connectivity check result:")
        logger.info(output)
    except subprocess.CalledProcessError as e:
        # Handle errors that may occur during the Kafka connectivity check
        logger.error("Error during Kafka connectivity check:")
        logger.error(e.output)