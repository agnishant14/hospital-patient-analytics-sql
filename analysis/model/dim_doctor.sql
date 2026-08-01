-- Doctor dimension. FullName is composed here so every consumer agrees.
SELECT DoctorID,
       FirstName + ' ' + LastName AS DoctorName,
       Gender,
       ExperienceYears
FROM dbo.Dim_Doctor
ORDER BY DoctorID;
