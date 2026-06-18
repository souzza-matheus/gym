package com.gymvision.session.config

import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import com.fasterxml.jackson.module.kotlin.readValue
import jakarta.servlet.FilterChain
import jakarta.servlet.http.HttpServletRequest
import jakarta.servlet.http.HttpServletResponse
import org.springframework.stereotype.Component
import org.springframework.web.filter.OncePerRequestFilter
import java.util.Base64

/**
 * Extrai academy_id do JWT (sem re-validar a assinatura — Kong já fez isso).
 * Disponibiliza como atributo de request "tenantAcademyId" para o service layer.
 */
@Component
class TenantFilter : OncePerRequestFilter() {

    private val mapper = jacksonObjectMapper()

    override fun doFilterInternal(
        request: HttpServletRequest,
        response: HttpServletResponse,
        filterChain: FilterChain,
    ) {
        val auth = request.getHeader("Authorization")
        if (auth != null && auth.startsWith("Bearer ")) {
            val token = auth.removePrefix("Bearer ").trim()
            extractAcademyId(token)?.let { request.setAttribute("tenantAcademyId", it) }
            extractRole(token)?.let { request.setAttribute("tenantRole", it) }
        }
        filterChain.doFilter(request, response)
    }

    private fun jwtPayload(token: String): Map<String, Any?>? = runCatching {
        val parts = token.split(".")
        if (parts.size < 2) return null
        val decoded = Base64.getUrlDecoder().decode(padBase64(parts[1]))
        mapper.readValue<Map<String, Any?>>(decoded)
    }.getOrNull()

    private fun padBase64(s: String): String {
        val pad = (4 - s.length % 4) % 4
        return s + "=".repeat(pad)
    }

    private fun extractAcademyId(token: String): String? =
        jwtPayload(token)?.get("academy_id") as? String

    private fun extractRole(token: String): String? =
        jwtPayload(token)?.get("role") as? String
}
