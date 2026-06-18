package com.gymvision.session.controller

import com.gymvision.session.service.CreateWorkoutPlanRequest
import com.gymvision.session.service.WorkoutPlanItemRequest
import com.gymvision.session.service.WorkoutPlanService
import org.springframework.http.HttpStatus
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.*
import java.util.UUID

@RestController
@RequestMapping("/api/v1/workout-plans")
class WorkoutPlanController(private val service: WorkoutPlanService) {

    @PostMapping
    fun create(@RequestBody req: CreateWorkoutPlanRequest) =
        ResponseEntity.status(HttpStatus.CREATED)
            .body(ApiResponse(true, service.create(req)))

    @GetMapping("/{id}")
    fun getById(@PathVariable id: UUID) =
        ResponseEntity.ok(ApiResponse(true, service.getById(id)))

    @GetMapping("/student/{studentId}")
    fun byStudent(@PathVariable studentId: UUID) =
        ResponseEntity.ok(ApiResponse(true, service.listByStudent(studentId)))

    @GetMapping("/academy/{academyId}")
    fun byAcademy(@PathVariable academyId: UUID) =
        ResponseEntity.ok(ApiResponse(true, service.listByAcademy(academyId)))

    @PutMapping("/{id}/items")
    fun updateItems(
        @PathVariable id: UUID,
        @RequestBody items: List<WorkoutPlanItemRequest>,
    ) = ResponseEntity.ok(ApiResponse(true, service.updateItems(id, items)))

    @DeleteMapping("/{id}")
    fun deactivate(@PathVariable id: UUID) =
        ResponseEntity.ok(ApiResponse(true, service.deactivate(id)))
}
