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


