package com.dreamsoftware.integrator.config;


import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.integration.annotation.IntegrationComponentScan;
import org.springframework.integration.channel.DirectChannel;
import org.springframework.integration.config.EnableIntegration;
import org.springframework.integration.core.GenericHandler;
import org.springframework.integration.dsl.IntegrationFlow;
import org.springframework.integration.endpoint.MessageProducerSupport;
import org.springframework.integration.kafka.dsl.Kafka;
import org.springframework.integration.mqtt.inbound.MqttPahoMessageDrivenChannelAdapter;
import org.springframework.integration.mqtt.support.DefaultPahoMessageConverter;
import org.springframework.kafka.core.ProducerFactory;
import org.springframework.messaging.MessageChannel;
import com.dreamsoftware.integrator.dto.CameraFogFrameDTO;

@Configuration
@EnableIntegration
@IntegrationComponentScan
public class IntegrationConfig {

    private static final Logger logger = LoggerFactory.getLogger(IntegrationConfig.class);

    @Value("${MQTT_BROKER}")
    private String mqttBroker;

    @Value("${MQTT_TOPIC}")
    private String mqttTopic;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private StringRedisTemplate redisTemplate;

    @Bean
    public MessageChannel mqttInputChannel() {
        return new DirectChannel();
    }

    @Bean
    public MessageChannel kafkaOutboundChannel() {
        return new DirectChannel();
    }

    @Bean
    public MessageProducerSupport mqttInbound() {
        MqttPahoMessageDrivenChannelAdapter adapter =
                new MqttPahoMessageDrivenChannelAdapter("tcp://" + mqttBroker, "clientId", mqttTopic);
        adapter.setCompletionTimeout(5000);
        adapter.setConverter(new DefaultPahoMessageConverter());
        adapter.setQos(1);
        return adapter;
    }

    @Bean
    public GenericHandler<String> messageHandler() {
        return (payload, headers) -> {
            try {
                logger.info("Received JSON: " + payload);
                CameraFogFrameDTO cameraFogFrameDTO = objectMapper.readValue(payload.replaceAll("'", "\""), CameraFogFrameDTO.class);
                String macAddress = cameraFogFrameDTO.getMacAddress();
                if (hasSession(macAddress)) {
                    logger.info("CameraFogFrameDTO mac: " + macAddress + "  allowed");
                    return cameraFogFrameDTO;
                } else {
                    logger.info("MAC: " + macAddress + " has not a valid session, payload was discarted");
                }
            } catch (JsonProcessingException e) {
                logger.error("Error parsing JSON: " + e.getMessage(), e);
                return null;
            }
            return null;
        };
    }

    @Bean
    public IntegrationFlow mqttToKafkaFlow(@Qualifier("kafkaProducerFactory") ProducerFactory<String, Object> kafkaProducerFactory) {
        return IntegrationFlow.from(mqttInbound())
                .channel(mqttInputChannel())
                .handle(messageHandler())
                .handle(Kafka.outboundChannelAdapter(kafkaProducerFactory)
                        .messageKey("mac_address")
                        .topic("iot-camera-frames"))
                .get();
    }

    private boolean hasSession(String macAddress) {
        logger.info("check session key: " + macAddress + "_session");
        return Boolean.TRUE.equals(redisTemplate.hasKey(macAddress + "_session"));
    }

    @PostConstruct
    public void logEnvironmentVariables() {
        System.out.println("MQTT Broker: " + mqttBroker);
        System.out.println("MQTT Topic: " + mqttTopic);
    }
}