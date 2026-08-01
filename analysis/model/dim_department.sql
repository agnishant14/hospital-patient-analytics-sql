-- Cleaned department dimension (Specialization is promoted to DepartmentName).
SELECT DepartmentID, DepartmentName, DepartmentCategory
FROM dbo.Dim_Department_Clean
ORDER BY DepartmentID;
