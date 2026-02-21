from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal



class Department(models.Model):

    name = models.CharField(max_length=150)
    image = models.ImageField(upload_to="media/", blank=True, null=True)

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
    email = models.EmailField(unique=True, blank=True, null=True)
    date_of_join = models.DateField()
    image = models.ImageField(upload_to='workers/', blank=True, null=True)
    posting = models.CharField(max_length=150)
    department_role = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name} ({self.worker_type})"
    

class Project(models.Model):

    PROJECT_CATEGORY = (
        ('client', 'Client'),
        ('company', 'Company'),
        ('internship', 'Internship'),
        ('academy', 'Academy'),
    )

    PROJECT_STATUS = (
        ('started','Started'),
        ('ongoing','Ongoing'),
        ('on_hold','On Hold'),
        ('canceled','Canceled'),
        ('finished','Finished'),
    )

    WORK_TYPE = (
        ('solo','Solo'),
        ('group','Group'),
    )

    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="projects")

    title = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=PROJECT_CATEGORY)
    work_type = models.CharField(max_length=10, choices=WORK_TYPE)
    start_date = models.DateField()
    status = models.CharField(max_length=20, choices=PROJECT_STATUS)

    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    github_link = models.URLField(blank=True, null=True)

    def clean(self):

        if self.category != 'company' and not self.amount:
            raise ValidationError("This project type requires amount")

    def __str__(self):
        return f"{self.title} ({self.category})"
    
class ProjectMember(models.Model):

    CONTRIBUTION = (
        ('gold','Gold'),
        ('silver','Silver'),
        ('copper','Copper'),
    )

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="members")
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name="project_memberships")

    contribution = models.CharField(max_length=10,default='gold', choices=CONTRIBUTION)

    class Meta:
        unique_together = ('project', 'worker')

    def __str__(self):
        return f"{self.worker.name} - {self.project.title}"

