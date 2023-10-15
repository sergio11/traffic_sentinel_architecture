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

	namespace :ServiceFoundationLayer do
		desc "Tasks related to the Service Foundation Layer"
		# Define tasks related to the Service Foundation Layer

		desc "Check Service Foundation layer Deployment File"
		task :check_deployment_file do
			puts "Check Platform Deployment File ..."
			raise "Deployment file not found, please check availability" unless File.file?("./services-foundation-layer/docker-compose.yml")
			puts "Platform Deployment File OK!"
		end

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
			config_json = File.read('config.json')
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
			config_json = File.read('config.json')
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

		desc "Start Service Foundation layer Containers"
		task :start => [ :check_docker_task, :login, :check_deployment_file  ] do
			puts "Start Service Foundation layer containers"
			puts `docker-compose -f ./services-foundation-layer/docker-compose.yml up -d 2>&1`
			puts "Waiting for Service Foundation layer start ..."
			sleep(60)
		end

		desc "Stop Service Foundation layer Containers"
		task :stop => [ :check_docker_task, :login, :check_deployment_file  ] do
			puts "Stop Service Foundation layer Containers"
			puts `docker-compose -f ./services-foundation-layer/docker-compose.yml stop 2>&1`
		end

		# New task that combines the initialization, enabling secrets, and preload tasks
		desc "Configure Service Foundation layer"
		task :configure => [:initialize_and_unseal, :enable_secrets, :preload_fog_nodes] do
		  puts "Service Foundation layer configured."
		end

		desc "Deploy Service Foundation layer Containers"
		task :deploy => [ :check_docker_task, :login, :check_deployment_file, :cleaning_environment_task, :start, :configure  ] do
			puts "Deploy Service Foundation layer Containers"
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
	end


	namespace :StreamProcessingLayer do
		desc "Tasks related to the Stream Processing Layer"
		
		desc "Build stream processing layer"
		task :build do
		puts "Build stream processing layer ..."
			image_info = [
				{ name: "ssanchez11/smart_highway_net_job_manager_flink:0.0.1", directory: "./stream-processing-layer/jobmanager" },
				{ name: "ssanchez11/smart_highway_net_task_manager_flink:0.0.1", directory: "./stream-processing-layer/taskmanager" }
			]
		
			image_info.each do |info|
				puts "Build Docker Image #{info[:name]}"
				puts `docker build -t #{info[:name]} -f #{info[:directory]}/Dockerfile ./stream-processing-layer`
				puts "Docker image #{info[:name]} has been created! trying to upload it!"
				puts `docker push #{info[:name]}`
			end
			puts `docker images`
		end
		

		desc "Check stream processing layer deployment file"	
		task :check_deployment_file do
			puts "Check stream processing layer deployment file ..."
			raise "Deployment file not found, please check availability" unless File.file?("./stream-processing-layer/docker-compose.yml")
			puts "Platform Deployment File OK!"
		end

		desc "Start stream processing layer containers"
		task :start => [ :check_docker_task, :login, :check_deployment_file  ] do
			puts "Start stream processing layer containers"
			puts `docker-compose -f ./stream-processing-layer/docker-compose.yml up -d 2>&1`
		end

		desc "Stop stream processing layer container"
		task :stop => [ :check_docker_task, :login, :check_deployment_file  ] do
			puts "Stop stream processing layer container"
			puts `docker-compose -f ./stream-processing-layer/docker-compose.yml stop 2>&1`
		end

		desc "Deploy stream processing layer container"
		task :deploy => [ :check_docker_task, :login, :check_deployment_file, :cleaning_environment_task, :start  ] do
			puts "Deploy stream processing layer container"
		end

		desc "Install and run VideoFrameProcessorFlink"
		task :install_job do
			compose_file_path = "./framework-extended-services-layer/docker-compose.yml"
			job_directory = "VideoFrameProcessor"  # Name of the Job directory
			job_file = "#{job_directory}/VideoFrameProcessorFlink.py"
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

			check_requirements_file_command = "docker-compose -f #{compose_file_path} exec -T jobmanager test -f /opt/flink/jobs/#{requirements_file}"
			system(check_requirements_file_command)

			if $?.success?
				# Install dependencies if requirements.txt
				puts "Installing Python dependencies from #{requirements_file} in the jobmanager container..."
				install_requirements_command = "docker-compose -f #{compose_file_path} exec -T jobmanager pip install -r /opt/flink/jobs/#{requirements_file}"
				system(install_requirements_command)
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
	  
	  
	namespace :FrameworkExtendedServiceLayer do
		desc "Tasks related to the Framework-Extended Service Layer"
		# Define tasks related to the Framework-Extended Service Layer

		desc "Build Framework Extended service layer"
		task :build do
			puts "Build Framework Extended service layer ..."
			image_info = [
				{ name: "ssanchez11/smart_highway_net_auth_service:0.0.1", directory: "./framework-extended-services-layer/auth" },
				{ name: "ssanchez11/smart_highway_net_provision_service:0.0.1", directory: "./framework-extended-services-layer/provision" },
				{ name: "ssanchez11/smart_highway_net_integrator_service:0.0.1", directory: "./framework-extended-services-layer/integrator" },
				{ name: "ssanchez11/smart_highway_net_notifier_service:0.0.1", directory: "./framework-extended-services-layer/notifier" },
			]

			image_info.each do |info|
				puts "Build Docker Image #{info[:name]}"
				puts `docker build -t #{info[:name]} -f #{info[:directory]}/Dockerfile #{info[:directory]}`
				puts "Docker image #{info[:name]} has been created! trying to upload it!"
				puts `docker push #{info[:name]}`
			end
			puts `docker images`
		end
		
		desc "Check Framework Extended service layer Deployment File"
		task :check_deployment_file do
			puts "Check Platform Deployment File ..."
			raise "Deployment file not found, please check availability" unless File.file?("./framework-extended-services-layer/docker-compose.yml")
			puts "Platform Deployment File OK!"
		end

		desc "Start framework extended service layer containers"
		task :start => [ :check_docker_task, :login, :check_deployment_file  ] do
			puts "Start framework extended service layer containers"
			puts `docker-compose -f ./framework-extended-services-layer/docker-compose.yml up -d 2>&1`
		end

		desc "Stop framework extended service layer container"
		task :stop => [ :check_docker_task, :login, :check_deployment_file  ] do
			puts "Stop framework extended service layer container"
			puts `docker-compose -f ./framework-extended-services-layer/docker-compose.yml stop 2>&1`
		end

		desc "Deploy framework extended service layer container"
		task :deploy => [ :check_docker_task, :login, :check_deployment_file, :cleaning_environment_task, :start  ] do
			puts "Deploy framework extended service layer container"
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
  