Copia del módulo **hr_expense_invoice** del PR https://github.com/OCA/hr-expense/pull/382 de OCA/hr-expense (Tecnativa/hr-expense 19.0-mig-hr_expense_invoice, commit 2d96df0),
renombrada para no chocar con el original. Reemplazar por **hr_expense_invoice** cuando el PR se
mergee en 19.0. No se puede instalar junto con el original.

This module should be used when a supplier invoice is paid by an
employee. It allows to set a supplier invoice for each expense line,
adding the corresponding journal items to transfer the debt to the
employee.

There are 1 way to reference expense to invoice.

1.  On expense, directly select one invoice.
