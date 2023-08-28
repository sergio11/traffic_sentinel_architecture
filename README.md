# Traffic Sentinel - An IoT Traffic Monitoring System

![Traffic Sentinel Logo](traffic_sentinel_logo.png)

Traffic Sentinel is a scalable IoT-based traffic monitoring system designed to process streaming data from IP cameras, apply intelligent vehicle detection using YOLO (You Only Look Once), and provide real-time insights into traffic patterns on roads. The system leverages Fog nodes for intermediate processing, Apache Flink for data processing, Redis for caching and session management, and MQTT for communication between nodes.

## Table of Contents

- [Introduction](#introduction)
- [Architecture Overview](#architecture-overview)
- [Technologies Used](#technologies-used)
- [Components](#components)
- [Getting Started](#getting-started)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)

## Introduction

Traffic congestion and road safety are critical concerns in modern urban environments. Traffic Sentinel addresses these challenges by providing a comprehensive IoT-based traffic monitoring solution. The system collects video streams from IP cameras deployed on roads and uses machine learning techniques to detect and track vehicles in real time. This data is then processed and analyzed to provide insights into traffic flow, congestion, and potential safety issues.

## Architecture Overview

Traffic Sentinel's architecture is designed to handle the complexities of real-time traffic data processing. It consists of the following key components:

- **Fog Nodes**: Intermediate processing nodes placed strategically to preprocess data from IP cameras, reducing the load on central servers.
- **Apache Flink**: A stream processing framework used for real-time data analysis, enabling tasks like vehicle detection using YOLO.
- **Redis**: A caching and session management tool used for storing temporary data, such as authentication sessions.
- **MQTT**: A lightweight messaging protocol used for communication between Fog nodes and central servers.

## Technologies Used

- **Python**: The main programming language used for developing various components of the system.
- **Flask**: A lightweight web framework used for building the provisioning service that provides camera information to Fog nodes.
- **MongoDB**: A NoSQL database used for storing camera information associated with MAC addresses of Fog nodes.
- **Redis**: An in-memory data store used for caching and session management.
- **Apache Flink**: A stream processing framework for real-time data analysis.
- **YOLO (You Only Look Once)**: A deep learning-based object detection model used for vehicle detection in video streams.
- **MQTT**: A lightweight messaging protocol for communication between Fog nodes and central servers.

## Components

The Traffic Sentinel system comprises the following components:

- **Fog Node**: Responsible for intermediate data processing and communication with IP cameras, Apache Flink, and central servers.
- **Provisioning Service**: A Flask-based web service that provides camera information to Fog nodes based on MAC addresses.
- **Apache Flink Jobs**: Real-time data processing tasks for vehicle detection using the YOLO model.
- **Redis Cache**: Used for caching authentication sessions and other temporary data.
- **MongoDB Database**: Stores camera information associated with MAC addresses.

## Getting Started

1. **Installation**: Clone the repository and install the required dependencies using the provided `requirements.txt` file.


2. **Configuration**: Configure the system by providing the necessary environment variables, such as MQTT broker, Redis host, MongoDB connection string, etc.

3. **Run the Components**: Start the Fog nodes, Apache Flink jobs, and the Flask-based Provisioning Service.

## Usage

1. **Authentication and Provisioning**: When a Fog node starts, it initiates the authentication process with the central server using CHAP. Upon successful authentication, it requests camera information from the Provisioning Service.

2. **Real-time Data Processing**: The Fog nodes capture video streams from IP cameras and preprocess the data. The processed data is then sent to Apache Flink for real-time analysis using YOLO for vehicle detection.

3. **Data Insights**: The analyzed data is used to generate insights into traffic patterns, congestion, and vehicle movement. These insights can be visualized through a dashboard or accessed through APIs.

## Contributing

Contributions are welcome! If you'd like to contribute to Traffic Sentinel, please follow the guidelines in [CONTRIBUTING.md](CONTRIBUTING.md).

## License

This project is licensed under the [MIT License](LICENSE).

---

## Credits

Traffic Sentinel is developed and maintained by Sergio Sánchez Sánchez. Special thanks to the open-source community and the contributors who have made this project possible.

---

