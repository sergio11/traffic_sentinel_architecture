package com.dreamsoftware.integrator.config;

import jakarta.annotation.PostConstruct;
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
import org.springframework.integration.core.GenericSelector;
import org.springframework.integration.dsl.IntegrationFlow;
import org.springframework.integration.dsl.Transformers;
import org.springframework.integration.endpoint.MessageProducerSupport;
import org.springframework.integration.kafka.dsl.Kafka;
import org.springframework.integration.mqtt.inbound.MqttPahoMessageDrivenChannelAdapter;
import org.springframework.integration.mqtt.support.DefaultPahoMessageConverter;
import org.springframework.kafka.core.ProducerFactory;
import org.springframework.messaging.MessageChannel;
import org.springframework.messaging.support.GenericMessage;

import java.util.Map;
import java.util.Objects;

@Configuration
@EnableIntegration
@IntegrationComponentScan
public class IntegrationConfig {

    @Value("${MQTT_BROKER}")
    private String mqttBroker;

    @Value("${MQTT_TOPIC}")
    private String mqttTopic;

    @Autowired
    private StringRedisTemplate redisTemplate;

    @PostConstruct
    public void logEnvironmentVariables() {
        System.out.println("MQTT Broker: " + mqttBroker);
        System.out.println("MQTT Topic: " + mqttTopic);
    }

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
    public GenericHandler<GenericMessage<Map<String, String>>> messageHandler() {
        return (message, headers) -> {
            Map<String, String> payload = message.getPayload();
            String macAddress = payload.get("mac_address");
            if (hasSession(macAddress)) {
                // Process the MQTT message here
                return message;
            }
            return null; // Discard messages without a session
        };
    }

    @Bean
    public IntegrationFlow mqttToKafkaFlow(@Qualifier("kafkaProducerFactory") ProducerFactory<String, Object> kafkaProducerFactory) {
        return IntegrationFlow.from(mqttInbound())
                .channel(mqttInputChannel())
                .handle(messageHandler())
                .filter((GenericSelector<GenericMessage<Map<String, String>>>) Objects::nonNull)
                .transform(Transformers.toJson()) // Transform the message to JSON format
                .channel(kafkaOutboundChannel())
                .handle(Kafka.outboundChannelAdapter(kafkaProducerFactory)
                        .messageKey("mac_address") // Use the 'mac_address' as the message key
                        .topicExpression("'iot-camera-frames'")) // Specify the Kafka topic
                .get();
    }

    private boolean hasSession(String macAddress) {
        return Boolean.TRUE.equals(redisTemplate.hasKey(macAddress + "_session"));
    }
}