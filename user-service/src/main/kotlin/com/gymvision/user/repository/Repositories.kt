package com.gymvision.user.repository

import com.gymvision.user.model.RefreshToken
import com.gymvision.user.model.User
import org.springframework.data.jpa.repository.JpaRepository
import org.springframework.data.jpa.repository.Modifying
import org.springframework.data.jpa.repository.Query
import java.time.Instant
import java.util.UUID

interface UserRepository : JpaRepository<User, UUID> {
    fun findByEmail(email: String): User?
    fun existsByEmail(email: String): Boolean
    fun findAllByAcademyIdAndActiveTrue(academyId: UUID): List<User>
    fun findAllByAcademyIdAndRoleAndActiveTrue(academyId: UUID, role: com.gymvision.user.model.UserRole): List<User>
}

interface AcademyRepository : JpaRepository<com.gymvision.user.model.Academy, UUID> {
    fun findByInviteCode(inviteCode: String): com.gymvision.user.model.Academy?
    fun existsByName(name: String): Boolean
}

interface RefreshTokenRepository : JpaRepository<RefreshToken, UUID> {
    fun findByTokenHash(tokenHash: String): RefreshToken?

    @Modifying
    @Query("UPDATE RefreshToken r SET r.revoked = true WHERE r.user.id = :userId")
    fun revokeAllByUserId(userId: UUID): Int

    @Modifying
    @Query("DELETE FROM RefreshToken r WHERE r.expiresAt < :now OR r.revoked = true")
    fun deleteExpiredAndRevoked(now: Instant): Int

    @Modifying
    @Query("DELETE FROM RefreshToken r WHERE r.user.id = :userId")
    fun deleteAllByUserId(userId: UUID): Int
}
