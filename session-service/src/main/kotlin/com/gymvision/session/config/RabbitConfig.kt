package com.gymvision.session.config

import org.springframework.amqp.core.*
import org.springframework.amqp.rabbit.connection.ConnectionFactory
import org.springframework.amqp.rabbit.core.RabbitTemplate
import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter
import org.springframework.context.annotation.Bean
import org.springframework.context.annotation.Configuration

@Configuration
class RabbitConfig {

    @Bean
    fun jsonMessageConverter() = Jackson2JsonMessageConverter()

    @Bean
    fun rabbitTemplate(cf: ConnectionFactory, converter: Jackson2JsonMessageConverter): RabbitTemplate =
        RabbitTemplate(cf).apply { messageConverter = converter }

    @Bean fun exerciseResultQueue() = Queue("gym.exercise.result", true)
    @Bean fun alertCreatedQueue() = Queue("gym.alert.created", true)
    @Bean fun sessionEndedQueue() = Queue("gym.session.ended", true)

    @Bean
    fun gymExchange() = TopicExchange("gym.events", true, false)

    @Bean fun bindExerciseResult(q: Queue, e: TopicExchange) =
        BindingBuilder.bind(exerciseResultQueue()).to(gymExchange()).with("exercise.result.#")

    @Bean fun bindAlertCreated(q: Queue, e: TopicExchange) =
        BindingBuilder.bind(alertCreatedQueue()).to(gymExchange()).with("alert.created.#")

    @Bean fun bindSessionEnded(q: Queue, e: TopicExchange) =
        BindingBuilder.bind(sessionEndedQueue()).to(gymExchange()).with("session.ended.#")
}
