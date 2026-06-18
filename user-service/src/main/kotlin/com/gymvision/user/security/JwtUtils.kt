package com.gymvision.user.security

import io.jsonwebtoken.Claims
import io.jsonwebtoken.Jwts
import io.jsonwebtoken.security.Keys
import org.springframework.beans.factory.annotation.Value
import org.springframework.stereotype.Component
import java.util.*
import javax.crypto.SecretKey

// ── JwtUtils ──────────────────────────────────────────────────────────────────
@Component
class JwtUtils(
    @Value("\${jwt.secret}") private val secret: String,
    @Value("\${jwt.expiration-ms}") private val expirationMs: Long,
    @Value("\${jwt.refresh-expiration-ms}") private val refreshExpirationMs: Long
) {

    private val signingKey: SecretKey by lazy {
        Keys.hmacShaKeyFor(secret.toByteArray())
    }

    fun generateAccessToken(userId: String, email: String, role: String, academyId: String? = null): String =
        buildToken(userId, email, role, academyId, expirationMs)

    fun generateRefreshToken(userId: String, email: String, role: String, academyId: String? = null): String =
        buildToken(userId, email, role, academyId, refreshExpirationMs)

    private fun buildToken(userId: String, email: String, role: String, academyId: String?, expMs: Long): String {
        val builder = Jwts.builder()
            .subject(userId)
            .claim("email", email)
            .claim("role", role)
            .issuedAt(Date())
            .expiration(Date(System.currentTimeMillis() + expMs))
        if (academyId != null) builder.claim("academy_id", academyId)
        return builder.signWith(signingKey).compact()
    }

    fun validateToken(token: String): Boolean = runCatching {
        getClaims(token)
        true
    }.getOrDefault(false)

    fun getUserIdFromToken(token: String): String = getClaims(token).subject

    fun getEmailFromToken(token: String): String = getClaims(token)["email"] as String

    fun getRoleFromToken(token: String): String = getClaims(token)["role"] as String

    fun getAcademyIdFromToken(token: String): String? = getClaims(token)["academy_id"] as? String

    private fun getClaims(token: String): Claims =
        Jwts.parser()
            .verifyWith(signingKey)
            .build()
            .parseSignedClaims(token)
            .payload
}
