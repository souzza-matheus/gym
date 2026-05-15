package com.gymvision.session.repository

import com.gymvision.session.model.*
import org.springframework.data.jpa.repository.JpaRepository
import org.springframework.data.jpa.repository.Query
import java.util.UUID

interface SessionRepository : JpaRepository<Session, UUID> {
    fun findAllByStudentId(studentId: UUID): List<Session>
    fun findAllByAcademyId(academyId: UUID): List<Session>
    fun findAllByStudentIdAndStatus(studentId: UUID, status: SessionStatus): List<Session>
}

interface RepRepository : JpaRepository<Rep, UUID> {
    fun findAllBySessionIdOrderByRepNumberAsc(sessionId: UUID): List<Rep>
    fun countBySessionId(sessionId: UUID): Long

    @Query("SELECT COALESCE(AVG(r.score), 0) FROM Rep r WHERE r.sessionId = :sessionId")
    fun avgScoreBySessionId(sessionId: UUID): Double
}

interface AlertRefRepository : JpaRepository<AlertRef, UUID> {
    fun findAllBySessionId(sessionId: UUID): List<AlertRef>
    fun findAllBySessionIdAndAcknowledgedFalse(sessionId: UUID): List<AlertRef>
}
