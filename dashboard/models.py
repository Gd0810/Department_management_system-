from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal



class Department(models.Model):

    name = models.CharField(max_length=150)
    image = models.ImageField(upload_to="departments/", blank=True, null=True)

    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)  # will store hashed password

    def __str__(self):
        return self.name


class Worker(models.Model):

    WORKER_TYPE = (
        ('staff', 'Staff'),
        ('intern', 'Intern'),
    )

    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="workers")

    worker_type = models.CharField(max_length=10, choices=WORKER_TYPE)
    name = models.CharField(max_length=150)
    date_of_join = models.DateField()
    image = models.ImageField(upload_to='workers/', blank=True, null=True)
    posting = models.CharField(max_length=150)
    department_role = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name} ({self.worker_type})"
