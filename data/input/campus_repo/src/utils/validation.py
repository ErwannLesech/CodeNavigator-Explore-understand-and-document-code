class ValidationError(Exception):
    pass


def validate_student_record(record):
    required_fields = ["student_id", "school_id", "first_name", "last_name", "email"]
    for field in required_fields:
        if field not in record or not record[field]:
            raise ValidationError(f"Missing required field: {field}")

    if not isinstance(record["student_id"], (int, str)):
        raise ValidationError("student_id must be integer or string")

    return True


def validate_school_record(record):
    required_fields = ["school_id", "name", "address", "city"]
    for field in required_fields:
        if field not in record or not record[field]:
            raise ValidationError(f"Missing required field: {field}")

    return True


def validate_purchase_record(record):
    required_fields = ["student_id", "item_id", "amount", "purchase_date"]
    for field in required_fields:
        if field not in record:
            raise ValidationError(f"Missing required field: {field}")

    if not isinstance(record["amount"], (int, float)) or record["amount"] < 0:
        raise ValidationError("amount must be positive number")

    return True


def validate_grade_record(record):
    required_fields = ["student_id", "grade_value", "grade_date", "subject"]
    for field in required_fields:
        if field not in record:
            raise ValidationError(f"Missing required field: {field}")

    if not 0 <= record["grade_value"] <= 20:
        raise ValidationError("grade_value must be between 0 and 20")

    return True
