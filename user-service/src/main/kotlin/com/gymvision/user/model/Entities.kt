package com.gymvision.user.model

import jakarta.persistence.*
import java.time.Instant
import java.util.UUID

// ── Academy ───────────────────────────────────────────────────────────────────
@Entity
@Table(name = "academies")
data class Academy(
    @Id @GeneratedValue(strategy = GenerationType.UUID)
    val id: UUID = UUID.randomUUID(),

    @Column(nullable = false, length = 100)
    val name: String,

    val address: String? = null,

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    val plan: AcademyPlan = AcademyPlan.FREE,

    val active: Boolean = true,

    @Column(name = "invite_code", unique = true, length = 12)
    val inviteCode: String? = null,

    @Column(name = "created_at", updatable = false)
    val createdAt: Instant = Instant.now(),

    @Column(name = "updated_at")
    var updatedAt: Instant = Instant.now()
)

enum class AcademyPlan { FREE, BASIC, PRO }

// ── User ──────────────────────────────────────────────────────────────────────
@Entity
@Table(name = "users")
data class User(
    @Id @GeneratedValue(strategy = GenerationType.UUID)
    val id: UUID = UUID.randomUUID(),

    @Column(nullable = false, length = 100)
    val name: String,

    @Column(nullable = false, unique = true, length = 150)
    val email: String,

    @Column(nullable = false)
    var password: String,

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    val role: UserRole,

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "academy_id")
    val academy: Academy? = null,

    var active: Boolean = true,

    @Column(name = "created_at", updatable = false)
    val createdAt: Instant = Instant.now(),

    @Column(name = "updated_at")
    var updatedAt: Instant = Instant.now()
)

enum class UserRole { STUDENT, TEACHER, ADMIN }

// ── RefreshToken ──────────────────────────────────────────────────────────────
@Entity
@Table(name = "refresh_tokens")
data class RefreshToken(
    @Id @GeneratedValue(strategy = GenerationType.UUID)
    val id: UUID = UUID.randomUUID(),

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    val user: User,

    @Column(name = "token_hash", nullable = false, unique = true)
    val tokenHash: String,

    @Column(name = "expires_at", nullable = false)
    val expiresAt: Instant,

    var revoked: Boolean = false,

    @Column(name = "created_at", updatable = false)
    val createdAt: Instant = Instant.now()
)
