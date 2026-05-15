package com.gymvision.user.controller

import com.gymvision.user.service.*
import jakarta.validation.Valid
import jakarta.validation.constraints.Email
import jakarta.validation.constraints.NotBlank
import jakarta.validation.constraints.Size
import org.springframework.http.HttpStatus
import org.springframework.http.ResponseEntity
import org.springframework.security.core.context.SecurityContextHolder
import org.springframework.web.bind.annotation.*
import java.util.UUID

// ── Request/Response wrappers ─────────────────────────────────────────────────
data class ApiResponse<T>(val success: Boolean, val data: T? = null, val message: String? = null)

data class LoginRequestBody(
    @field:NotBlank @field:Email val email: String,
    @field:NotBlank val password: String
)

data class RegisterRequestBody(
    @field:NotBlank @field:Size(min = 2, max = 100) val name: String,
    @field:NotBlank @field:Email val email: String,
    @field:NotBlank @field:Size(min = 6) val password: String
)

// ── AuthController ────────────────────────────────────────────────────────────
@RestController
@RequestMapping("/api/v1/auth")
class AuthController(private val authService: AuthService) {

    @PostMapping("/login")
    fun login(@Valid @RequestBody body: LoginRequestBody): ResponseEntity<ApiResponse<AuthResponse>> {
        val response = authService.login(LoginRequest(body.email, body.password))
        return ResponseEntity.ok(ApiResponse(success = true, data = response))
    }

    @PostMapping("/refresh")
    fun refresh(@RequestBody body: Map<String, String>): ResponseEntity<ApiResponse<AuthResponse>> {
        val token = body["refreshToken"] ?: return ResponseEntity.badRequest()
            .body(ApiResponse(success = false, message = "refreshToken é obrigatório"))
        val response = authService.refreshToken(RefreshRequest(token))
        return ResponseEntity.ok(ApiResponse(success = true, data = response))
    }

    @PostMapping("/logout")
    fun logout(): ResponseEntity<ApiResponse<Unit>> {
        val userId = UUID.fromString(SecurityContextHolder.getContext().authentication.principal as String)
        authService.logout(userId)
        return ResponseEntity.ok(ApiResponse(success = true, message = "Logout realizado com sucesso"))
    }
}

// ── UserController ────────────────────────────────────────────────────────────
@RestController
@RequestMapping("/api/v1/users")
class UserController(private val authService: AuthService, private val userService: UserService) {

    @PostMapping("/register")
    fun register(@Valid @RequestBody body: RegisterRequestBody): ResponseEntity<ApiResponse<AuthResponse>> {
        val response = authService.register(RegisterRequest(body.name, body.email, body.password))
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse(success = true, data = response))
    }

    @GetMapping("/me")
    fun me(): ResponseEntity<ApiResponse<UserDto>> {
        val userId = UUID.fromString(SecurityContextHolder.getContext().authentication.principal as String)
        return ResponseEntity.ok(ApiResponse(success = true, data = userService.findById(userId)))
    }

    @GetMapping("/{id}")
    fun getById(@PathVariable id: UUID): ResponseEntity<ApiResponse<UserDto>> =
        ResponseEntity.ok(ApiResponse(success = true, data = userService.findById(id)))

    @GetMapping("/academy/{academyId}")
    fun listByAcademy(@PathVariable academyId: UUID): ResponseEntity<ApiResponse<List<UserDto>>> =
        ResponseEntity.ok(ApiResponse(success = true, data = userService.listByAcademy(academyId)))
}

// ── GlobalExceptionHandler ────────────────────────────────────────────────────
@RestControllerAdvice
class GlobalExceptionHandler {

    @ExceptionHandler(IllegalArgumentException::class)
    fun handleBadRequest(ex: IllegalArgumentException) =
        ResponseEntity.badRequest().body(ApiResponse<Unit>(success = false, message = ex.message))

    @ExceptionHandler(NoSuchElementException::class)
    fun handleNotFound(ex: NoSuchElementException) =
        ResponseEntity.status(HttpStatus.NOT_FOUND).body(ApiResponse<Unit>(success = false, message = ex.message))

    @ExceptionHandler(IllegalStateException::class)
    fun handleConflict(ex: IllegalStateException) =
        ResponseEntity.status(HttpStatus.CONFLICT).body(ApiResponse<Unit>(success = false, message = ex.message))
}
