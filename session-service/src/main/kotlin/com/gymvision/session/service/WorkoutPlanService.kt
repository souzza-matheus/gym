package com.gymvision.session.service

import com.gymvision.session.model.WorkoutPlan
import com.gymvision.session.model.WorkoutPlanItem
import com.gymvision.session.repository.WorkoutPlanItemRepository
import com.gymvision.session.repository.WorkoutPlanRepository
import org.springframework.stereotype.Service
import org.springframework.transaction.annotation.Transactional
import java.util.UUID

// ── DTOs ──────────────────────────────────────────────────────────────────────

data class WorkoutPlanItemRequest(
    val exerciseType: String,
    val sets: Int = 3,
    val repsPerSet: Int = 10,
    val loadKg: Double? = null,
    val notes: String? = null,
    val orderIndex: Int = 0,
)

data class CreateWorkoutPlanRequest(
    val academyId: UUID,
    val studentId: UUID,
    val professorId: UUID,
    val name: String,
    val dayOfWeek: Int? = null,
    val items: List<WorkoutPlanItemRequest> = emptyList(),
)

data class WorkoutPlanItemDto(
    val id: UUID,
    val exerciseType: String,
    val sets: Int,
    val repsPerSet: Int,
    val loadKg: Double?,
    val notes: String?,
    val orderIndex: Int,
)

data class WorkoutPlanDto(
    val id: UUID,
    val studentId: UUID,
    val academyId: UUID,
    val professorId: UUID,
    val name: String,
    val dayOfWeek: Int?,
    val active: Boolean,
    val items: List<WorkoutPlanItemDto>,
)

private fun WorkoutPlanItem.toDto() = WorkoutPlanItemDto(
    id = id, exerciseType = exerciseType, sets = sets,
    repsPerSet = repsPerSet, loadKg = loadKg, notes = notes, orderIndex = orderIndex,
)

// ── WorkoutPlanService ────────────────────────────────────────────────────────

@Service
class WorkoutPlanService(
    private val planRepo: WorkoutPlanRepository,
    private val itemRepo: WorkoutPlanItemRepository,
) {

    @Transactional
    fun create(req: CreateWorkoutPlanRequest): WorkoutPlanDto {
        val plan = planRepo.save(
            WorkoutPlan(
                academyId = req.academyId,
                studentId = req.studentId,
                professorId = req.professorId,
                name = req.name,
                dayOfWeek = req.dayOfWeek,
            )
        )
        val items = req.items.mapIndexed { idx, item ->
            itemRepo.save(
                WorkoutPlanItem(
                    planId = plan.id,
                    exerciseType = item.exerciseType.uppercase(),
                    sets = item.sets,
                    repsPerSet = item.repsPerSet,
                    loadKg = item.loadKg,
                    notes = item.notes,
                    orderIndex = item.orderIndex.takeIf { it != 0 } ?: idx,
                )
            )
        }
        return plan.toDto(items.map { it.toDto() })
    }

    fun getById(id: UUID): WorkoutPlanDto {
        val plan = planRepo.findById(id).orElseThrow { NoSuchElementException("Plano não encontrado: $id") }
        val items = itemRepo.findAllByPlanIdOrderByOrderIndexAsc(id)
        return plan.toDto(items.map { it.toDto() })
    }

    fun listByStudent(studentId: UUID): List<WorkoutPlanDto> =
        planRepo.findAllByStudentIdAndActiveTrue(studentId).map { plan ->
            plan.toDto(itemRepo.findAllByPlanIdOrderByOrderIndexAsc(plan.id).map { it.toDto() })
        }

    fun listByAcademy(academyId: UUID): List<WorkoutPlanDto> =
        planRepo.findAllByAcademyIdAndActiveTrue(academyId).map { plan ->
            plan.toDto(itemRepo.findAllByPlanIdOrderByOrderIndexAsc(plan.id).map { it.toDto() })
        }

    @Transactional
    fun updateItems(planId: UUID, items: List<WorkoutPlanItemRequest>): WorkoutPlanDto {
        val plan = planRepo.findById(planId).orElseThrow { NoSuchElementException("Plano não encontrado: $planId") }
        itemRepo.deleteAllByPlanId(planId)
        val saved = items.mapIndexed { idx, item ->
            itemRepo.save(
                WorkoutPlanItem(
                    planId = planId,
                    exerciseType = item.exerciseType.uppercase(),
                    sets = item.sets,
                    repsPerSet = item.repsPerSet,
                    loadKg = item.loadKg,
                    notes = item.notes,
                    orderIndex = item.orderIndex.takeIf { it != 0 } ?: idx,
                )
            )
        }
        return plan.toDto(saved.map { it.toDto() })
    }

    @Transactional
    fun deactivate(planId: UUID): WorkoutPlanDto {
        val plan = planRepo.findById(planId).orElseThrow { NoSuchElementException("Plano não encontrado: $planId") }
        val updated = planRepo.save(plan.copy(active = false))
        val items = itemRepo.findAllByPlanIdOrderByOrderIndexAsc(planId)
        return updated.toDto(items.map { it.toDto() })
    }

    private fun WorkoutPlan.toDto(items: List<WorkoutPlanItemDto>) = WorkoutPlanDto(
        id = id, studentId = studentId, academyId = academyId,
        professorId = professorId, name = name, dayOfWeek = dayOfWeek,
        active = active, items = items,
    )
}
