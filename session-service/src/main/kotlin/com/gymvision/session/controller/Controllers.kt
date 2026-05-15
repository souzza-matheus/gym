package com.gymvision.session.controller

import com.gymvision.session.service.*
import org.springframework.http.HttpStatus
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.*
import java.util.UUID

data class ApiResponse<T>(val success: Boolean, val data: T? = null, val message: String? = null)

@RestController
@RequestMapping("/api/v1/sessions")
class SessionController(private val sessionService: SessionService) {

    @PostMapping
    fun create(@RequestBody req: CreateSessionRequest) =
        ResponseEntity.status(HttpStatus.CREATED)
            .body(ApiResponse(true, sessionService.createSession(req)))

    @GetMapping("/{id}")
    fun get(@PathVariable id: UUID) =
        ResponseEntity.ok(ApiResponse(true, sessionService.getSession(id)))

    @GetMapping("/student/{studentId}")
    fun byStudent(@PathVariable studentId: UUID) =
        ResponseEntity.ok(ApiResponse(true, sessionService.listByStudent(studentId)))

    @GetMapping("/academy/{academyId}")
    fun byAcademy(@PathVariable academyId: UUID) =
        ResponseEntity.ok(ApiResponse(true, sessionService.listByAcademy(academyId)))

    @PostMapping("/{id}/reps")
    fun recordRep(@PathVariable id: UUID, @RequestBody req: RecordRepRequest) =
        ResponseEntity.status(HttpStatus.CREATED)
            .body(ApiResponse(true, sessionService.recordRep(id, req)))

    @GetMapping("/{id}/reps")
    fun getReps(@PathVariable id: UUID) =
        ResponseEntity.ok(ApiResponse(true, sessionService.getReps(id)))

    @PostMapping("/{id}/end")
    fun endSession(@PathVariable id: UUID) =
        ResponseEntity.ok(ApiResponse(true, sessionService.endSession(id)))

    @GetMapping("/{id}/summary")
    fun summary(@PathVariable id: UUID) =
        ResponseEntity.ok(ApiResponse(true, sessionService.getSession(id)))

    @GetMapping("/{id}/alerts")
    fun getAlerts(@PathVariable id: UUID) =
        ResponseEntity.ok(ApiResponse(true, sessionService.getAlerts(id)))

    @PostMapping("/alerts/{alertId}/ack")
    fun ackAlert(@PathVariable alertId: UUID): ResponseEntity<ApiResponse<Unit>> {
        sessionService.acknowledgeAlert(alertId)
        return ResponseEntity.ok(ApiResponse(true, message = "Alerta confirmado"))
    }
}

@RestControllerAdvice
class SessionExceptionHandler {
    @ExceptionHandler(NoSuchElementException::class)
    fun notFound(ex: NoSuchElementException) =
        ResponseEntity.status(HttpStatus.NOT_FOUND).body(ApiResponse<Unit>(false, message = ex.message))

    @ExceptionHandler(IllegalStateException::class)
    fun conflict(ex: IllegalStateException) =
        ResponseEntity.status(HttpStatus.CONFLICT).body(ApiResponse<Unit>(false, message = ex.message))
}
