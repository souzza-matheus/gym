// Root build — configurações compartilhadas entre todos os subprojetos Kotlin/JVM
plugins {
    kotlin("jvm") version "1.9.20" apply false
    kotlin("plugin.spring") version "1.9.20" apply false
    id("org.springframework.boot") version "3.2.0" apply false
    id("io.spring.dependency-management") version "1.1.4" apply false
}

subprojects {
    repositories {
        mavenCentral()
    }
}
