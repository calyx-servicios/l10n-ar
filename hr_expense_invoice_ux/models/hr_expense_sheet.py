##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import Command, api, models
from odoo.exceptions import ValidationError


class HrExpenseSheet(models.Model):
    _inherit = "hr.expense.sheet"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            expenses = self._get_resulting_expenses(self.env["hr.expense"], vals.get("expense_line_ids"))
            method = self._check_lines_payment_method(expenses)
            if method and not vals.get("payment_method_line_id"):
                vals["payment_method_line_id"] = method.id
        return super().create(vals_list)

    def write(self, vals):
        if "expense_line_ids" in vals and "payment_method_line_id" not in vals:
            for sheet in self:
                expenses = self._get_resulting_expenses(sheet.expense_line_ids, vals["expense_line_ids"])
                self._check_lines_payment_method(expenses)
        return super().write(vals)

    @api.depends("selectable_payment_method_line_ids")
    def _compute_payment_method_line_id(self):
        # hr_expense_sheet_calyx vuelve al primer método seleccionable cada vez que cambian las líneas,
        # y se lo impone a todos los gastos del informe sin avisar. Conservamos el elegido.
        keep = self.filtered(lambda x: x.payment_method_line_id in x.selectable_payment_method_line_ids)
        return super(HrExpenseSheet, self - keep)._compute_payment_method_line_id()

    def _check_lines_payment_method(self, expenses):
        """Los gastos pagados por la compañía de un mismo informe deben tener el mismo método de
        pago. Se controla antes de agrupar porque después el informe impone el suyo a las líneas."""
        company_expenses = expenses.filtered(lambda x: x.payment_mode == "company_account")
        methods = company_expenses.payment_method_line_id
        if len(methods) > 1:
            raise ValidationError(
                self.env._(
                    "Todos los gastos del informe deben tener el mismo método de pago:\n%s",
                    "\n".join(
                        f"- {expense.name}: {expense.payment_method_line_id.display_name}"
                        for expense in company_expenses
                    ),
                )
            )
        return methods

    def _get_resulting_expenses(self, expenses, commands):
        """Gastos que quedan en el informe después de aplicar los comandos x2many. Los que se
        crean dentro del informe (CREATE) no cuentan: toman el método de pago del informe."""
        for command in commands or []:
            if not isinstance(command, (list, tuple)):
                continue
            if command[0] == Command.SET:
                expenses = self.env["hr.expense"].browse(command[2])
            elif command[0] == Command.LINK:
                expenses |= self.env["hr.expense"].browse(command[1])
            elif command[0] in (Command.UNLINK, Command.DELETE):
                expenses -= self.env["hr.expense"].browse(command[1])
            elif command[0] == Command.CLEAR:
                expenses = self.env["hr.expense"]
        return expenses
