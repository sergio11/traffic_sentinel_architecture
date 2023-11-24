require 'json'
require 'redis'
require 'vault'
require 'digest'
task default: %w[SmartHighwayNet:status]

namespace :SmartHighwayNet do

	desc "Authenticating with existing credentials"
	task :login do
		puts `docker login 2>&1`
	end

	desc "Cleaning Environment Task"
	task :cleaning_environment_task do
		puts "Cleaning Environment"
		puts `docker image prune -af`
		puts `docker volume prune -f 2>&1`
	end

	desc "Status Containers"
	task :status do
		puts "Show Containers Status"
		puts `docker-compose ps 2>&1`
	end

    desc "Check Docker and Docker Compose Task"
	task :check_docker_task do
		puts "Check Docker and Docker Compose ..."
		if which('docker') && which('docker-compose')
			show_docker_version
			show_docker_compose_version
		else
			raise "Please check that Docker and Docker Compose are visible and accessible in the PATH"
		end
	end

	namespace :DataStorageLayer do
		desc "Tasks related to the Data Storage Layer"
		# Define tasks related to the Data Storage Layer

		desc "Check data storage layer deployment file"	
		task :check_deployment_file do
			puts "Check data storage layer deployment file ..."
			raise "Deployment file not found, please check availability" unless File.file?("./data-storage-layer/docker-compose.yml")
			puts "Platform Deployment File OK!"
		end

		desc "Start data storage layer containers"
		task :start => [ :check_docker_task, :login, :check_deployment_file  ] do
			puts "Start data storage layer containers"
			puts `docker-compose -f ./data-storage-layer/docker-compose.yml up -d 2>&1`
			puts "Waiting for data storage layer start ..."
			sleep(60)
		end

		desc "Stop data storage layer container"
		task :stop => [ :check_docker_task, :login, :check_deployment_file  ] do
			puts "Stop data storage layer container"
			puts `docker-compose -f ./data-storage-layer/docker-compose.yml stop 2>&1`
		end

		desc "Deploy data storage layer container"
		task :deploy => [ :check_docker_task, :login, :check_deployment_file, :cleaning_environment_task, :start  ] do
			puts "Deploy data storage layer container"
		end

		# This Rake task 'initialize_and_unseal' is designed to automate the initialization and unsealing process of a Vault instance.
		# It interacts with a Redis instance to retrieve the Vault root token and unseal keys, and checks the status of the Vault using a Docker container.
		# If the Vault is sealed and uninitialized, it initializes the Vault, stores the generated unseal keys and root token in Redis,
		# and then proceeds to unseal the Vault using the obtained keys. Finally, it displays the Vault's status and the root token stored in Redis,
		# ensuring that the Vault is unsealed and ready for use. If the Vault is already initialized and unsealed, it confirms the status and retrieves the root token.
		desc "Initialize and Unseal"
		task :initialize_and_unseal do
			redis = Redis.new(host: 'localhost', port: 6379)
			root_token = redis.get('vault_root_token')
			unseal_keys = redis.lrange('unseal_keys', 0, -1)
			vault_status = `docker exec -it vault vault status`
			puts "Checking Vault status..."
			puts vault_status
			if  /Sealed\s+true/.match(vault_status)
				if /Initialized\s+false/.match(vault_status)
					puts "Initializing Vault..."
					vault_init_output = `docker exec -it vault vault operator init -key-shares=1 -key-threshold=1 -format=json`
					vault_init_data = JSON.parse(vault_init_output)
					unseal_keys = vault_init_data['unseal_keys_b64']
				
					puts "Storing unseal keys in Redis..."
					redis.del('unseal_keys')
					unseal_keys.each do |key|
						redis.rpush('unseal_keys', key)
					end
				
					root_token = vault_init_data['root_token']
					redis.set('vault_root_token', root_token)
					puts "Root token stored in Redis: #{root_token}"
				end
				puts "Unsealing Vault..."
				unseal_keys.each do |key|
					puts `docker exec -it vault vault operator unseal #{key}`
				end
				puts "Vault unsealed."
				if root_token.nil?
					puts "No root token found in Redis."
				else
					puts "Root token from Redis: #{root_token}"
				end
			elsif  /Sealed\s+false/.match(vault_status)
				puts "Vault is already initialized and unsealed."
				puts "Root token from Redis: #{root_token}"
			else
				puts "Vault status is unknown."
			end
		end

		# This Rake task 'seal' automates the sealing process of a Vault instance.
		# It interacts with a Redis instance to retrieve the Vault root token, which is necessary for sealing the Vault.
		# Upon obtaining the root token from Redis, it checks the status of the Vault using a Docker container.
		# If the Vault is both unsealed and initialized, the task proceeds to seal the Vault using the obtained root token by logging in and initiating the sealing operation.
		# Once sealed, the Vault becomes inaccessible for security purposes.
		# However, if the Vault is already sealed or not initialized, the sealing operation is not performed, and an appropriate message is displayed indicating the inability to seal the Vault.
		desc "Seal"
		task :seal do
			redis = Redis.new(host: 'localhost', port: 6379)
			root_token = redis.get('vault_root_token')
			if root_token.nil?
				puts "Root token not found in Redis. Please initialize and unseal Vault first."
			else
				vault_status = `docker exec -it vault vault status`
				puts "Checking Vault status..."
				puts vault_status
				if /Sealed\s+false/.match(vault_status) && /Initialized\s+true/.match(vault_status)
					puts "Sealing Vault..."
					puts `docker exec -it vault vault login #{root_token}`
					puts `docker exec -it vault vault operator seal`
					puts "Vault sealed."
				else
					puts "It is not possible sealing the vault"
				end
				
			end
		end

		# This Rake task 'enable_secrets' facilitates the enabling of secrets within a Vault instance.
		# It connects to a Redis instance to retrieve the Vault root token required for authentication.
		# Subsequently, it checks the status of the Vault using a Docker container to ensure it's both unsealed and initialized.
		# Upon meeting these conditions, the task proceeds by logging into Vault using the root token and enables the secrets engine for storing secrets.
		# Specifically, it enables a key-value (kv) secrets engine at the specified path 'secret/data/fog-nodes-v1'.
		# However, if the Vault is already sealed or not initialized, the operation to enable secrets is not allowed, and an appropriate message is displayed.
		desc "Enable Secrets"
		task :enable_secrets do
			redis = Redis.new(host: 'localhost', port: 6379)
			root_token = redis.get('vault_root_token')
			vault_status = `docker exec -it vault vault status`
			puts "Start enabling secrets - checking Vault status..."
			puts vault_status
			if  /Sealed\s+false/.match(vault_status) && /Initialized\s+true/.match(vault_status)
				puts `docker exec -it vault vault login #{root_token}`
				puts `docker exec -it vault vault secrets enable -path="secret/data/fog-nodes-v1" kv`
			else
				puts "Operation not allowed"
			end
		end

		# This Rake task 'preload_fog_nodes' serves the purpose of preloading fog node configurations into Vault.
		# It involves configurations for Redis and Vault for data retrieval and storage.
		# The Redis client is set up to connect to a local Redis instance to retrieve the Vault root token.
		# The task configures the Vault client to communicate with the local Vault server using the obtained root token.
		# It reads configuration data from a JSON file containing information about fog nodes and their configurations.
		# Each fog node's data is preprocessed, and its information is stored securely in Vault.
		# The task clears existing data at a specified Vault endpoint before storing new information.
		# Specifically, fog node configurations such as passwords and code hashes are stored in Vault using unique identifiers derived from the MAC addresses of the nodes.
		# However, in case of errors during data storage in Vault, appropriate error messages are displayed.
		desc "Preload Fog Nodes in Vault"
		task :preload_fog_nodes do
			# Redis Configuration
			redis_client = Redis.new(host: "localhost", port: 6379, db: 0)

			# Vault Configuration
			VAULT_ADDRESS = 'http://localhost:8200'
			# Retrieve the VAULT_TOKEN from Redis
			VAULT_TOKEN = redis_client.get('vault_root_token')
			Vault.configure do |config|
				config.address = VAULT_ADDRESS
				config.token = VAULT_TOKEN
			end
			# Load configuration from a JSON file
			config_json = File.read('config/fog_nodes_config.json')
			config_data = JSON.parse(config_json)

			code_path = config_data['code_path']
			code_hash = Digest::SHA256.file(code_path).hexdigest

			fog_nodes = config_data['fog_nodes']

			# Vault Secret Endpoint
			vault_secret_endpoint = config_data['vault_secret_endpoint']

			# Clear the existing data at the endpoint
			begin
				Vault.logical.delete(vault_secret_endpoint)
				puts "Cleared existing data at '#{vault_secret_endpoint}' endpoint"
			rescue Vault::HTTPClientError => e
				puts "Error clearing existing data: #{e.response.body}"
			end

			fog_nodes.each do |node|
				mac_without_colons = node['mac_address'].delete(":")
				begin
				# Store the new information in Vault
				Vault.logical.write("#{vault_secret_endpoint}/#{mac_without_colons}", data: node['password'], code_hash: code_hash)
				puts "Fog node with MAC #{node['mac_address']} with password: #{node['password']} and code hash: #{code_hash} preloaded in Vault"
				rescue Vault::HTTPClientError => e
				puts "Error from Vault server: #{e.response.body}"
				end
			end
		end

		# This Rake task 'retrieve_fog_nodes' facilitates the retrieval of fog node information securely stored in Vault.
		# It involves configurations for Redis and Vault for data retrieval and communication.
		# The Redis client connects to a local Redis instance to retrieve the Vault root token necessary for authentication with Vault.
		# Subsequently, the task configures the Vault client to communicate with the local Vault server using the obtained root token.
		# The task reads configuration data from a JSON file ('config.json') containing endpoint information for the fog nodes stored in Vault.
		# It retrieves fog node information by listing the available data at the specified Vault endpoint.
		# For each fog node listed, it retrieves and displays the associated information such as the MAC address, password, and hash code securely stored in Vault.
		# However, in case of any errors during the retrieval process from Vault, appropriate error messages are displayed.
		desc "Retrieve Fog Nodes from Vault"
		task :retrieve_fog_nodes do
			# Redis Configuration
			redis_client = Redis.new(host: "localhost", port: 6379, db: 0)

			# Vault Configuration
			VAULT_ADDRESS = 'http://localhost:8200'
			# Retrieve the VAULT_TOKEN from Redis
			VAULT_TOKEN = redis_client.get('vault_root_token')
			puts "Vault token from redis: #{VAULT_TOKEN}"
			Vault.configure do |config|
				config.address = VAULT_ADDRESS
				config.token = VAULT_TOKEN
			end

			# Load configuration from a JSON file
			config_json = File.read('config/fog_nodes_config.json')
			config_data = JSON.parse(config_json)

			# Vault Secret Endpoint
			vault_secret_endpoint = config_data['vault_secret_endpoint']

			begin
				response = Vault.logical.list(vault_secret_endpoint)
				fog_nodes = response.map(&:to_s)
				fog_nodes.each do |mac_address|
				puts "Retrieving information for Fog Node with MAC Address: #{mac_address}"
				response = Vault.logical.read("#{vault_secret_endpoint}/#{mac_address}")
				puts "Fog Node with MAC Address #{mac_address}"
				puts "Password: #{response.data[:data]}"
				puts "Hashcode: #{response.data[:code_hash]}"
				puts "---"
				end
			rescue Vault::HTTPClientError => e
				puts "Error from Vault server: #{e.response.body}"
			end
		end

		# New task that combines the initialization, enabling secrets, and preload tasks
		desc "Configure Service Foundation layer"
		task :configure => [:initialize_and_unseal, :enable_secrets, :preload_fog_nodes] do
		  puts "Service Foundation layer configured."
		end
	end

	namespace :DataOrchestrationLayer do
		desc "Data Orchestration Layer: Responsible for orchestrating data flows between systems and components, ensuring data integration, transformation, and delivery."
		
		desc "Check data orchestration layer deployment file"	
		task :check_deployment_file do
			puts "Check data orchestration layer deployment file ..."
			raise "Deployment file not found, please check availability" unless File.file?("./data-storage-layer/docker-compose.yml")
			puts "Platform Deployment File OK!"
		end

		desc "Start data orchestration layer containers"
		task :start => [ :check_docker_task, :login, :check_deployment_file  ] do
			puts "Start data orchestration layer containers"
			puts `docker-compose -f ./data-orchestration-layer/docker-compose.yml up -d 2>&1`
		end

		desc "Stop data orchestration layer container"
		task :stop => [ :check_docker_task, :login, :check_deployment_file  ] do
			puts "Stop data orchestration layer container"
			puts `docker-compose -f ./data-orchestration-layer/docker-compose.yml stop 2>&1`
		end

		desc "Deploy data orchestration layer container"
		task :deploy => [ :check_docker_task, :login, :check_deployment_file, :cleaning_environment_task, :start  ] do
			puts "Deploy data orchestration layer container"
		end
	end
	
	namespace :ManagementAndMonitoringLayer do
		desc "Tasks related to the Management And Monitoring Layer"
	  
		desc "Check management and monitoring layer deployment file"	
		task :check_deployment_file do
			puts "Check management and monitoring layer deployment file ..."
			raise "Deployment file not found, please check availability" unless File.file?("./management-monitoring-layer/docker-compose.yml")
			puts "Platform Deployment File OK!"
		end

		desc "Start management and monitoring layer containers"
		task :start => [ :check_docker_task, :login, :check_deployment_file  ] do
			puts "Start management and monitoring layer containers"
			puts `docker-compose -f ./management-monitoring-layer/docker-compose.yml up -d 2>&1`
		end

		desc "Stop management and monitoring layer container"
		task :stop => [ :check_docker_task, :login, :check_deployment_file  ] do
			puts "Stop management and monitoring layer container"
			puts `docker-compose -f ./management-monitoring-layer/docker-compose.yml stop 2>&1`
		end

		desc "Deploy management and monitoring layer container"
		task :deploy => [ :check_docker_task, :login, :check_deployment_file, :cleaning_environment_task, :start  ] do
			puts "Deploy management and monitoring layer container"
		end
	  end

	namespace :RealTimeDataProcessingLayer do
		desc "Tasks related to the Real-Time Data Processing Layer"
		
		desc "Build stream processing layer"
		task :build do
		puts "Build stream processing layer ..."
			image_info = [
				{ name: "ssanchez11/smart_highway_net_job_manager_flink:0.0.1", directory: "./real-time-data-processing-layer/jobmanager" },
				{ name: "ssanchez11/smart_highway_net_task_manager_flink:0.0.1", directory: "./real-time-data-processing-layer/taskmanager" }
			]
		
			image_info.each do |info|
				puts "Build Docker Image #{info[:name]}"
				puts `docker build -t #{info[:name]} -f #{info[:directory]}/Dockerfile ./real-time-data-processing-layer`
				puts "Docker image #{info[:name]} has been created! trying to upload it!"
				puts `docker push #{info[:name]}`
			end
			puts `docker images`
		end
		

		desc "Check stream processing layer deployment file"	
		task :check_deployment_file do
			puts "Check stream processing layer deployment file ..."
			raise "Deployment file not found, please check availability" unless File.file?("./real-time-data-processing-layer/docker-compose.yml")
			puts "Platform Deployment File OK!"
		end

		desc "Start stream processing layer containers"
		task :start => [ :check_docker_task, :login, :check_deployment_file  ] do
			puts "Start stream processing layer containers"
			puts `docker-compose -f ./real-time-data-processing-layer/docker-compose.yml up -d 2>&1`
		end

		desc "Stop stream processing layer container"
		task :stop => [ :check_docker_task, :login, :check_deployment_file  ] do
			puts "Stop stream processing layer container"
			puts `docker-compose -f ./real-time-data-processing-layer/docker-compose.yml stop 2>&1`
		end

		desc "Deploy stream processing layer container"
		task :deploy => [ :check_docker_task, :login, :check_deployment_file, :cleaning_environment_task, :start  ] do
			puts "Deploy stream processing layer container"
		end

		desc "Install and run VideoFrameProcessorFlink"
		task :install_job do
			compose_file_path = "./real-time-data-processing-layer/docker-compose.yml"
			job_directory = "VideoFrameProcessor"  # Name of the Job directory
			job_file = "#{job_directory}/main.py"
			requirements_file = "#{job_directory}/requirements.txt"

			# Check if the Job directory exists in the jobmanager container
			check_directory_command = "docker-compose -f #{compose_file_path} exec -T jobmanager test -d /opt/flink/jobs/#{job_directory}"
			system(check_directory_command)

			if $?.success?
				puts "The #{job_directory} directory exists in the jobmanager container."
			else
				puts "Error: The #{job_directory} directory does not exist in the jobmanager container."
				exit 1
			end

			# Check if the Job Python file exists in the jobmanager container
			check_file_command = "docker-compose -f #{compose_file_path} exec -T jobmanager test -f /opt/flink/jobs/#{job_file}"
			system(check_file_command)

			if $?.success?
				puts "The #{job_file} file exists in the jobmanager container."
			else
				puts "Error: The #{job_file} file does not exist in the jobmanager container."
				exit 1
			end

			# Check if requirements.txt exists in the jobmanager container
			check_requirements_file_command = "docker-compose -f #{compose_file_path} exec -T jobmanager test -f /opt/flink/jobs/#{requirements_file}"
			system(check_requirements_file_command)

			if $?.success?
				# Install Python dependencies from requirements.txt in the jobmanager container
				puts "Installing Python dependencies from #{requirements_file} in the jobmanager container..."
				install_requirements_command = "docker-compose -f #{compose_file_path} exec -T jobmanager pip install --no-cache-dir -r /opt/flink/jobs/#{requirements_file}"
				system(install_requirements_command)

				# Install Python dependencies in the taskmanager container as well
				puts "Installing Python dependencies from #{requirements_file} in the taskmanager container..."
				install_requirements_command_taskmanager = "docker-compose -f #{compose_file_path} exec -T taskmanager pip install --no-cache-dir -r /opt/flink/jobs/#{requirements_file}"
				system(install_requirements_command_taskmanager)
			end

			# Run the Flink program in Python in the job-manager container
			flink_command = "docker-compose exec -T jobmanager /opt/flink/bin/flink run --python /opt/flink/jobs/#{job_file}"
			system(flink_command)

			# Check the exit code
			if $?.success?
				puts "#{job_file} executed successfully in the jobmanager container."
			else
				puts "Error: #{job_file} exited with an invalid exit code in the jobmanager container."
				exit 1
			end
		end
	end

	namespace :DataServicesLayer do
		desc "Tasks related to the Data Services Layer"
		# Define tasks related to the Data Services Layer

		desc "Build data services layer"
		task :build do
			puts "Build data services layer ..."
			image_info = [
				{ name: "ssanchez11/smart_highway_net_fog_service:0.0.1", dockerfile: "./data-services-layer/fog/Dockerfile" },
				{ name: "ssanchez11/smart_highway_net_provision_service:0.0.1", dockerfile: "./data-services-layer/provision/Dockerfile" },
				{ name: "ssanchez11/smart_highway_net_notifier_service:0.0.1", dockerfile: "./data-services-layer/notifier/Dockerfile" },
				{ name: "ssanchez11/smart_highway_net_cameras_service:0.0.1", dockerfile: "./data-services-layer/cameras/Dockerfile" },
				{ name: "ssanchez11/smart_highway_net_users_service:0.0.1", dockerfile: "./data-services-layer/users/Dockerfile" },
				{ name: "ssanchez11/smart_highway_net_stream_service:0.0.1", dockerfile: "./data-services-layer/stream/Dockerfile" }
			]

			image_info.each do |info|
				puts "Build Docker Image #{info[:name]}"
				puts `docker build -t #{info[:name]} -f #{info[:dockerfile]} ./data-services-layer`
				puts "Docker image #{info[:name]} has been created! trying to upload it!"
				puts `docker push #{info[:name]}`
			end
			puts `docker images`
		end

		desc "Check admin user status"
		task :check_admin_user do
			require 'net/http'

			uri = URI.parse('http://localhost:5003/users/check-admin')
			request = Net::HTTP::Get.new(uri)
			response = Net::HTTP.start(uri.hostname, uri.port) { |http| http.request(request) }

			if response.code == '200'
				puts "Admin user status: #{response.body}"
			else
				puts "Failed to check admin user status. HTTP Error: #{response.code}"
			end
		end

		desc "Preload cameras"
		task :preload_cameras => [ :check_admin_user ] do
			# Endpoint for authentication
			auth_uri = URI.parse('http://localhost:5003/users/authenticate')
			auth_credentials = { username: 'root', password: 'trafficsentinel00' }
			
			# Make a POST request to authenticate
			auth_request = Net::HTTP.post(auth_uri, auth_credentials.to_json, 'Content-Type' => 'application/json')
			
			if auth_request.code == '200'
				auth_response = JSON.parse(auth_request.body)
				session_token = auth_response['session_token']
				puts "Auth successfully, session token #{session_token}"
				# Read cameras configuration from JSON file
				cameras_file = File.read('config/cameras_config.json')
				cameras_data = JSON.parse(cameras_file)
				
				# Register each camera using the obtained session token
				cameras_data['cameras'].each do |camera|
					register_uri = URI.parse('http://localhost:5002/cameras/register')
					headers = {
						'Content-Type' => 'application/json',
						'Authentication' => session_token
					}
					puts "Register camera #{camera["camera_name"]}"
					
					# Make a POST request to register each camera
					register_request = Net::HTTP.post(register_uri, camera.to_json, headers)
					
					if register_request.code == 200
						puts "Camera '#{camera['camera_name']}' registered successfully."
					else
						puts "Failed to register camera '#{camera['camera_name']}'. HTTP Error: #{register_request.code}"
					end
				end
			else
				puts "Authentication failed. HTTP Error: #{auth_request.code}"
			end
		end
		
		desc "Check  data services layer Deployment File"
		task :check_deployment_file do
			puts "Check Platform Deployment File ..."
			raise "Deployment file not found, please check availability" unless File.file?("./data-services-layer/docker-compose.yml")
			puts "Platform Deployment File OK!"
		end

		desc "Start data services layer containers"
		task :start => [ :check_docker_task, :login, :check_deployment_file  ] do
			puts "Start data services layer containers"
			puts `docker-compose -f ./data-services-layer/docker-compose.yml up -d 2>&1`
		end

		desc "Stop data services layer container"
		task :stop => [ :check_docker_task, :login, :check_deployment_file  ] do
			puts "Stop data services layer container"
			puts `docker-compose -f ./data-services-layer/docker-compose.yml stop 2>&1`
		end

		desc "Deploy data services layer container"
		task :deploy => [ :check_docker_task, :login, :check_deployment_file, :cleaning_environment_task, :start  ] do
			puts "Deploy data services layer container"
		end
	end
	  
	namespace :FogStreamingLayer do
		desc "Tasks related to the Fog Streaming Layer"
		# Define tasks related to the Fog Streaming Layer

		desc "Build the Docker image for the Fog node"
		task :build do
			puts "Building the Docker image for the Fog node..."
			fog_directory_path = "fog-stream-processing-layer/fog"
			image_name = "ssanchez11/smart_highway_net_fog_node:0.0.1"
			build_command = "docker build -t #{image_name} -f #{fog_directory_path}/Dockerfile #{fog_directory_path}"
			puts `#{build_command}`
			puts "Docker image #{image_name} has been created! trying to upload it!"
			puts `docker push #{image_name}`
		end

		desc "Check Fog streaming layer Deployment File"
		task :check_deployment_file do
			puts "Check Platform Deployment File ..."
			raise "Deployment file not found, please check availability" unless File.file?("./fog-stream-processing-layer/docker-compose.yml")
			puts "Platform Deployment File OK!"
		end

		desc "Start fog streaming layer containers"
		task :start => [ :check_docker_task, :login, :check_deployment_file  ] do
			puts "Start fog streaming layer containers"
			puts `docker-compose -f ./fog-stream-processing-layer/docker-compose.yml up -d 2>&1`
		end

		desc "Stop fog streaming layer container"
		task :stop => [ :check_docker_task, :login, :check_deployment_file  ] do
			puts "Stop fog streaming layer container"
			puts `docker-compose -f ./fog-stream-processing-layer/docker-compose.yml stop 2>&1`
		end

		desc "Deploy fog streaming layer container"
		task :deploy => [ :check_docker_task, :login, :check_deployment_file, :cleaning_environment_task, :start  ] do
			puts "Deploy fog streaming layer container"
		end
	end

	## Utils Functions

	def show_docker_version
	  puts `docker version 2>&1`
	end

	def show_docker_compose_version
	  puts `docker-compose version 2>&1`
	end

	# Cross-platform way of finding an executable in the $PATH.
	# which('ruby') #=> /usr/bin/ruby
	def which(cmd)
	  exts = ENV['PATHEXT'] ? ENV['PATHEXT'].split(';') : ['']
	  ENV['PATH'].split(File::PATH_SEPARATOR).each do |path|
	    exts.each { |ext|
	      exe = File.join(path, "#{cmd}#{ext}")
	      return exe if File.executable?(exe) && !File.directory?(exe)
	    }
	  end
	  return nil
	end

end
  