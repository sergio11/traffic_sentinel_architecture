task default: %w[flink:start]

namespace :flink do

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

		desc "Start Platform Containers"
		task :start => [ :check_docker_task, :login, :check_deployment_file  ] do
			puts "Start docker containers"
            system("docker-compose up -d")
            #puts "Wait"
            #sleep(10)
            #puts "Depoy Py-Flink program"
            #system("docker exec -it flink-taskmanager /bin/bash -c 'mkdir -p /job && cp /host/your_program.py /job'")
            #system("docker exec -it flink-taskmanager /bin/bash -c 'flink run /job/your_program.py'")
		end

		desc "Stop Platform Containers"
		task :stop => [ :check_docker_task, :login, :check_deployment_file  ] do
			puts "Stop Platform Containers"
			puts `docker-compose stop 2>&1`
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
  