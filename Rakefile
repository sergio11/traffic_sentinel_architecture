require 'json'
require 'redis'
require 'vault'
task default: %w[SmartHighwayNet:start]

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

	desc "Check Platform Deployment File"
	task :check_deployment_file do
		puts "Check Platform Deployment File ..."
		raise "Deployment file not found, please check availability" unless File.file?("./docker-compose.yml")
		puts "Platform Deployment File OK!"
	end

	namespace :configuration do 

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
				else
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
			puts "Checking Vault status..."
			puts vault_status
			if  /Sealed\s+false/.match(vault_status) && /Initialized\s+true/.match(vault_status)
				puts `docker exec -it vault vault login #{root_token}`
				puts `docker exec -it vault vault secrets enable -path="fog-nodes-v1" kv`
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
		
			# Preload Fog nodes in Vault
			fog_nodes = [
			{ mac_address: '02:42:ac:11:00:02', password: '9#Fg5aP@qL1' }
			# Add more fog nodes as needed
			]
		
			fog_nodes.each do |node|
				begin
					Vault.logical.write("fog-nodes-v1/#{node[:mac_address]}", data: node[:password])
					puts "Fog node with MAC #{node[:mac_address]} with password: #{node[:password]} preloaded in Vault"
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
			Vault.configure do |config|
				config.address = VAULT_ADDRESS
				config.token = VAULT_TOKEN
			end

			begin
				response = Vault.logical.list('fog-nodes-v1')
				fog_nodes = response.map(&:to_s)
				fog_nodes.each do |mac_address|
					response = Vault.logical.read("fog-nodes-v1/#{mac_address}")
					puts "Fog Node with MAC Address #{mac_address}:"
					puts "Password: #{response.data[:data]}"
					puts "---"
				end
			rescue Vault::HTTPClientError => e
				puts "Error from Vault server: #{e.response.body}"
			end
		end

		# New task that combines the initialization, enabling secrets, and preload tasks
		desc "Finalize Deployment"
		task :finalize_deploy => [:initialize_and_unseal, :enable_secrets, :preload_fog_nodes] do
		  puts "Final deployment steps completed."
		end

	end


	desc "Start Platform Containers"
	task :start => [ :check_docker_task, :login, :check_deployment_file  ] do
		puts "Start docker containers"
        puts `docker-compose up -d`
		puts "Waiting for platform start ..."
        sleep(60)
	end

	desc "Stop Platform Containers"
	task :stop => [ :check_docker_task, :login, :check_deployment_file  ] do
		puts "Stop Platform Containers"
		puts `docker-compose stop 2>&1`
	end

	desc "Deploy Platform Containers"
	task :deploy => [ :check_docker_task, :login, :check_deployment_file, :cleaning_environment_task, :start, "SmartHighwayNet:configuration:finalize_deploy"  ] do
		puts "Deploy platform containers"
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
  