package com.gymvision.user.service

import com.gymvision.user.model.RefreshToken
import com.gymvision.user.model.User
import com.gymvision.user.model.UserRole
import com.gymvision.user.repository.RefreshTokenRepository
import com.gymvision.user.repository.UserRepository
import com.gymvision.user.security.JwtUtils
import org.springframework.security.crypto.password.PasswordEncoder
import org.springframework.stereotype.Service
import org.springframework.transaction.annotation.Transactional
import java.security.MessageDigest
import java.time.Instant
import java.util.Base64
import java.util.UUID

// ── DTOs ──────────────────────────────────────────────────────────────────────
data class LoginRequest(val email: String, val password: String)
data class RegisterRequest(val name: String, val email: String, val password: String, val role: UserRole = UserRole.STUDENT)
data class RefreshRequest(val refreshToken: String)

data class AuthResponse(
    val accessToken: String,
    val refreshToken: String,
    val tokenType: String = "Bearer",
    val expiresIn: Long = 900,
    val user: UserDto
)

data class UserDto(
    val id: UUID,
    val name: String,
    val email: String,
    val role: UserRole,
    val academyId: UUID?
)

fun User.toDto() = UserDto(id = id, name = name, email = email, role = role, academyId = academy?.id)

// ── AuthService ───────────────────────────────────────────────────────────────
@Service
class AuthService(
    private val userRepository: UserRepository,
    private val refreshTokenRepository: RefreshTokenRepository,
    private val passwordEncoder: PasswordEncoder,
    private val jwtUtils: JwtUtils
) {

    @Transactional
    fun login(request: LoginRequest): AuthResponse {
        val user = userRepository.findByEmail(request.email)
            ?: throw IllegalArgumentException("Credenciais inválidas")

        if (!user.active) throw IllegalStateException("Usuário inativo")

        if (!passwordEncoder.matches(request.password, user.password))
            throw IllegalArgumentException("Credenciais inválidas")

        return generateTokenPair(user)
    }

    @Transactional
    fun register(request: RegisterRequest): AuthResponse {
        if (userRepository.existsByEmail(request.email))
            throw IllegalArgumentException("Email já cadastrado: ${request.email}")

        val user = userRepository.save(
            User(
                name = request.name,
                email = request.email,
                password = passwordEncoder.encode(request.password),
                role = request.role
            )
        )

        return generateTokenPair(user)
    }

    @Transactional
    fun refreshToken(request: RefreshRequest): AuthResponse {
        val hash = hashToken(request.refreshToken)
        val stored = refreshTokenRepository.findByTokenHash(hash)
            ?: throw IllegalArgumentException("Refresh token inválido")

        if (stored.revoked || stored.expiresAt.isBefore(Instant.now()))
            throw IllegalArgumentException("Refresh token expirado ou revogado")

        // Rotaciona o refresh token (invalida o anterior)
        stored.copy(revoked = true).also { refreshTokenRepository.save(it) }

        return generateTokenPair(stored.user)
    }

    @Transactional
    fun logout(userId: UUID) {
        refreshTokenRepository.revokeAllByUserId(userId)
    }

    private fun generateTokenPair(user: User): AuthResponse {
        val accessToken  = jwtUtils.generateAccessToken(user.id.toString(), user.email, user.role.name)
        val refreshToken = jwtUtils.generateRefreshToken(user.id.toString(), user.email, user.role.name)

        // Salva o hash do refresh token (nunca o token em si)
        refreshTokenRepository.save(
            RefreshToken(
                user = user,
                tokenHash = hashToken(refreshToken),
                expiresAt = Instant.now().plusMillis(7 * 24 * 60 * 60 * 1000L)
            )
        )

        return AuthResponse(
            accessToken = accessToken,
            refreshToken = refreshToken,
            user = user.toDto()
        )
    }

    private fun hashToken(token: String): String {
        val digest = MessageDigest.getInstance("SHA-256").digest(token.toByteArray())
        return Base64.getUrlEncoder().withoutPadding().encodeToString(digest)
    }
}

// ── UserService ───────────────────────────────────────────────────────────────
@Service
class UserService(
    private val userRepository: UserRepository,
    private val passwordEncoder: PasswordEncoder
) {

    fun findById(id: UUID): UserDto =
        userRepository.findById(id).orElseThrow { NoSuchElementException("Usuário não encontrado: $id") }.toDto()

    fun findByEmail(email: String): UserDto =
        (userRepository.findByEmail(email) ?: throw NoSuchElementException("Usuário não encontrado: $email")).toDto()

    fun listByAcademy(academyId: UUID): List<UserDto> =
        userRepository.findAllByAcademyIdAndActiveTrue(academyId).map { it.toDto() }

    @Transactional
    fun deactivate(id: UUID) {
        val user = userRepository.findById(id).orElseThrow { NoSuchElementException("Usuário não encontrado: $id") }
        userRepository.save(user.copy(active = false))
    }
}
