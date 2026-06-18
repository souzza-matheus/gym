package com.gymvision.user.service

import com.gymvision.user.model.Academy
import com.gymvision.user.model.AcademyPlan
import com.gymvision.user.model.RefreshToken
import com.gymvision.user.model.User
import com.gymvision.user.model.UserRole
import com.gymvision.user.repository.AcademyRepository
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
data class RegisterRequest(
    val name: String,
    val email: String,
    val password: String,
    val role: UserRole = UserRole.STUDENT,
    val inviteCode: String? = null,
)
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
    val academyId: UUID?,
    val academyName: String? = null,
)

data class UserDataExport(
    val profile: UserDto,
    val exportedAt: String,
    val dataNotice: String,
)

data class AcademyDto(
    val id: UUID,
    val name: String,
    val address: String?,
    val plan: AcademyPlan,
    val active: Boolean,
    val inviteCode: String?,
    val createdAt: Instant,
)

fun Academy.toDto() = AcademyDto(id = id, name = name, address = address, plan = plan,
    active = active, inviteCode = inviteCode, createdAt = createdAt)

fun User.toDto() = UserDto(id = id, name = name, email = email, role = role,
    academyId = academy?.id, academyName = academy?.name)

// ── AuthService ───────────────────────────────────────────────────────────────
@Service
class AuthService(
    private val userRepository: UserRepository,
    private val academyRepository: AcademyRepository,
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

        val academy = request.inviteCode?.let {
            academyRepository.findByInviteCode(it.uppercase())
                ?: throw IllegalArgumentException("Código de convite inválido: ${request.inviteCode}")
        }

        val user = userRepository.save(
            User(
                name = request.name,
                email = request.email,
                password = passwordEncoder.encode(request.password),
                role = request.role,
                academy = academy,
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
        val aid = user.academy?.id?.toString()
        val accessToken  = jwtUtils.generateAccessToken(user.id.toString(), user.email, user.role.name, aid)
        val refreshToken = jwtUtils.generateRefreshToken(user.id.toString(), user.email, user.role.name, aid)

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

    fun listByAcademy(academyId: UUID, role: UserRole? = null): List<UserDto> =
        if (role != null)
            userRepository.findAllByAcademyIdAndRoleAndActiveTrue(academyId, role).map { it.toDto() }
        else
            userRepository.findAllByAcademyIdAndActiveTrue(academyId).map { it.toDto() }

    @Transactional
    fun deactivate(id: UUID) {
        val user = userRepository.findById(id).orElseThrow { NoSuchElementException("Usuário não encontrado: $id") }
        userRepository.save(user.copy(active = false))
    }

    @Transactional
    fun deleteAccount(userId: UUID, refreshTokenRepository: RefreshTokenRepository) {
        refreshTokenRepository.deleteAllByUserId(userId)
        userRepository.deleteById(userId)
    }

    fun exportData(userId: UUID): UserDataExport {
        val user = userRepository.findById(userId).orElseThrow { NoSuchElementException("Usuário não encontrado: $userId") }
        return UserDataExport(
            profile = user.toDto(),
            exportedAt = Instant.now().toString(),
            dataNotice = "Dados de sessões e análises ficam retidos por 30 dias após exclusão da conta.",
        )
    }

    @Transactional
    fun joinAcademy(userId: UUID, inviteCode: String, academyRepository: AcademyRepository): UserDto {
        val user = userRepository.findById(userId).orElseThrow { NoSuchElementException("Usuário não encontrado") }
        val academy = academyRepository.findByInviteCode(inviteCode.uppercase())
            ?: throw IllegalArgumentException("Código de convite inválido: $inviteCode")
        return userRepository.save(user.copy(academy = academy)).toDto()
    }
}

// ── AcademyService ────────────────────────────────────────────────────────────
data class CreateAcademyRequest(
    val name: String,
    val address: String? = null,
    val plan: AcademyPlan = AcademyPlan.FREE,
)

@Service
class AcademyService(private val academyRepository: AcademyRepository) {

    fun list(): List<AcademyDto> = academyRepository.findAll().map { it.toDto() }

    fun getById(id: UUID): AcademyDto =
        academyRepository.findById(id).orElseThrow { NoSuchElementException("Academia não encontrada: $id") }.toDto()

    fun getByInviteCode(code: String): AcademyDto =
        (academyRepository.findByInviteCode(code.uppercase())
            ?: throw NoSuchElementException("Código inválido: $code")).toDto()

    @Transactional
    fun create(req: CreateAcademyRequest): AcademyDto {
        if (academyRepository.existsByName(req.name))
            throw IllegalArgumentException("Academia já existe com este nome: ${req.name}")
        val code = generateCode(req.name)
        val academy = academyRepository.save(
            Academy(name = req.name, address = req.address, plan = req.plan, inviteCode = code)
        )
        return academy.toDto()
    }

    private fun generateCode(name: String): String {
        val prefix = name.filter { it.isLetterOrDigit() }.uppercase().take(6).padEnd(6, 'X')
        val suffix = (1000..9999).random()
        return "${prefix}${suffix}".take(12)
    }
}
