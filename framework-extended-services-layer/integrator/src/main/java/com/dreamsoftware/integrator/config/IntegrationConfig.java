package com.dreamsoftware.integrator.config;

import jakarta.annotation.PostConstruct;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.common.serialization.StringSerializer;
import org.springframework.beans.factory.annotation.Autowired;
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
import org.springframework.integration.endpoint.MessageProducerSupport;
import org.springframework.integration.kafka.dsl.Kafka;
import org.springframework.integration.mqtt.inbound.MqttPahoMessageDrivenChannelAdapter;
import org.springframework.integration.mqtt.support.DefaultPahoMessageConverter;
import org.springframework.kafka.core.DefaultKafkaProducerFactory;
import org.springframework.kafka.core.ProducerFactory;
import org.springframework.kafka.support.serializer.JsonSerializer;
import org.springframework.messaging.Message;
import org.springframework.messaging.MessageChannel;

import java.util.HashMap;
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

    @Value("${KAFKA_BROKER}")
    private String kafkaBroker;

    @Value("${KAFKA_TOPIC}")
    private String kafkaTopic;

    @Autowired
    private StringRedisTemplate redisTemplate;


    @PostConstruct
    public void logEnvironmentVariables() {
        System.out.println("MQTT Broker: " + mqttBroker);
        System.out.println("MQTT Topic: " + mqttTopic);
        System.out.println("Kafka Broker: " + kafkaBroker);
        System.out.println("Kafka Topic: " + kafkaTopic);
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
                new MqttPahoMessageDrivenChannelAdapter(mqttBroker, "clientId", mqttTopic);
        adapter.setCompletionTimeout(5000);
        adapter.setConverter(new DefaultPahoMessageConverter());
        adapter.setQos(1);
        return adapter;
    }

    @Bean
    public GenericHandler<Message<?>> messageHandler() {
        return (message, headers) -> {
            String macAddress = headers.get("mqtt_topic", String.class);
            if (hasSession(macAddress)) {
                // Process the MQTT message here
                return message;
            }
            return null; // Discard messages without a session
        };
    }

    @Bean
    public IntegrationFlow mqttToKafkaFlow() {
        return IntegrationFlow.from(mqttInbound())
                .channel(mqttInputChannel())
                .handle(messageHandler())
                .filter((GenericSelector<Message<?>>) Objects::nonNull)
                .channel(kafkaOutboundChannel())
                .handle(Kafka.outboundChannelAdapter(kafkaProducerFactory())
                        .messageKey(m -> m.getHeaders().get("mqtt_topic"))
                        .topicExpression("headers['kafka_topic']"))
                .get();
    }

    @Bean
    public ProducerFactory<String, Object> kafkaProducerFactory() {
        Map<String, Object> configProps = new HashMap<>();
        configProps.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, kafkaBroker);
        configProps.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        configProps.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, JsonSerializer.class);
        return new DefaultKafkaProducerFactory<>(configProps);
    }

    private boolean hasSession(String macAddress) {
        return Boolean.TRUE.equals(redisTemplate.hasKey(macAddress + "_session"));
    }
}
