# Part of Odoo. See LICENSE file for full copyright and licensing details.

# -*- coding: utf-8 -*-
from odoo import fields, models, tools


class HrAppraisalSkillReport(models.Model):
    _auto = False
    _name = 'hr.appraisal.skill.report'
    _description = 'Appraisal Skills Report'
    _order = 'employee_id, skill_type_id, skill_id'

    id = fields.Id()
    display_name = fields.Char(related='employee_id.name')
    create_date = fields.Date(string='Create Date', readonly=True)
    
    employee_id = fields.Many2one('hr.employee', readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    department_id = fields.Many2one('hr.department', readonly=True)
    skill_id = fields.Many2one('hr.skill', readonly=True)
    skill_type_id = fields.Many2one('hr.skill.type', readonly=True)

    current_skill_level_id = fields.Many2one('hr.skill.level', string="Current Level", readonly=True)
    current_level_progress = fields.Float(string="Current Progress", readonly=True, aggregator='avg')

    previous_skill_level_id = fields.Many2one('hr.skill.level', string="Previous Level", readonly=True)
    previous_level_progress = fields.Float(string="Previous Progress", readonly=True, aggregator='avg')

    second_level_progress = fields.Float(string="Second Eval Progress", readonly=True)
    first_level_progress = fields.Float(string="First Eval Progress", readonly=True)

    justification = fields.Char(readonly=True)

    evolution = fields.Selection([
        ('improvement', 'Improvement'),
        ('same', 'Same'),
        ('just_added', 'Just added'),
        ('decline', 'Decline'),
    ], string='Evolution', readonly=True)

    evolution_sequence = fields.Integer(string='Evolution Sequence')
    progress_evolution = fields.Float(string="Progress Evolution", readonly=True, aggregator='avg')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)

        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                WITH ranked_skills AS (
                    SELECT
                        s.id AS appraisal_skill_id,
                        s.employee_id,
                        e.company_id,
                        e.department_id,
                        s.skill_id,
                        s.justification,
                        s.skill_type_id,
                        sl.id AS current_skill_level_id,
                        sl.level_progress / 100.0 AS current_level_progress,
                        sl_p.id AS previous_skill_level_id,
                        sl_p.level_progress / 100.0 AS previous_level_progress,
                        (sl.level_progress - COALESCE(sl_p.level_progress, 0)) / 100.0 AS progress_evolution,
                        CASE
                            WHEN sl.level_progress > COALESCE(sl_p.level_progress, 0) THEN 'improvement'
                            WHEN sl.level_progress < COALESCE(sl_p.level_progress, 0) THEN 'decline'
                            WHEN sl_p.level_progress IS NULL THEN 'just_added'
                            ELSE 'same'
                        END AS evolution,
                        a.create_date AS appraisal_date,
                        ROW_NUMBER() OVER (
                            PARTITION BY s.employee_id, s.skill_id
                            ORDER BY a.create_date DESC
                        ) AS rank
                    FROM hr_appraisal_skill s
                    JOIN hr_appraisal a ON a.id = s.appraisal_id AND a.state = 'done'
                    JOIN hr_employee e ON e.id = s.employee_id AND e.active IS TRUE
                    JOIN hr_skill_level sl ON sl.id = s.skill_level_id
                    LEFT JOIN hr_skill_level sl_p ON sl_p.id = s.previous_skill_level_id
                    JOIN hr_skill_type st ON st.id = s.skill_type_id AND st.active IS TRUE
                )
                SELECT
                    row_number() OVER () AS id,
                    employee_id,
                    company_id,
                    department_id,
                    skill_id,
                    skill_type_id,
                    MAX(CASE WHEN rank = 1 THEN current_skill_level_id END) AS current_skill_level_id,
                    MAX(CASE WHEN rank = 1 THEN current_level_progress END) AS current_level_progress,
                    MAX(CASE WHEN rank = 2 THEN current_level_progress END) AS previous_level_progress,
                    MAX(CASE WHEN rank = 3 THEN current_level_progress END) AS second_level_progress,
                    MAX(CASE WHEN rank = 4 THEN current_level_progress END) AS first_level_progress,
                    MAX(CASE WHEN rank = 1 THEN previous_skill_level_id END) AS previous_skill_level_id,
                    MAX(CASE WHEN rank = 1 THEN justification END) AS justification,
                    MAX(CASE WHEN rank = 1 THEN evolution END) AS evolution,
                    MAX(CASE WHEN rank = 1 THEN progress_evolution END) AS progress_evolution,
                    MAX(CASE WHEN rank = 1 THEN DATE(appraisal_date) END) AS create_date,
                    MAX(CASE WHEN rank = 1 THEN 1
                             WHEN rank = 2 THEN 2
                             WHEN rank = 3 THEN 3
                             WHEN rank = 4 THEN 4 END) AS evolution_sequence
                FROM ranked_skills
                WHERE rank <= 4
                GROUP BY employee_id, skill_id, skill_type_id, company_id, department_id
            )
        """)