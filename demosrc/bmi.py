"""Calculate and classify adult BMI using kilograms and metres."""

import argparse
import math


def calculate_bmi(weight_kg: float, height_m: float) -> float:
    """Return BMI for a positive weight in kilograms and height in metres."""
    if not math.isfinite(weight_kg) or weight_kg <= 0:
        raise ValueError("Weight must be a positive, finite number.")
    if not math.isfinite(height_m) or height_m <= 0:
        raise ValueError("Height must be a positive, finite number.")

    bmi = weight_kg / height_m / height_m
    if not math.isfinite(bmi) or bmi <= 0:
        raise ValueError("Weight and height produce an out-of-range BMI.")
    return bmi


def bmi_category(bmi: float) -> str:
    """Return the standard adult BMI category."""
    if not math.isfinite(bmi) or bmi <= 0:
        raise ValueError("BMI must be a positive, finite number.")
    if bmi < 18.5:
        return "Underweight"
    if bmi < 25:
        return "Healthy weight"
    if bmi < 30:
        return "Overweight"
    return "Obesity"


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate adult BMI.")
    parser.add_argument("weight_kg", type=float, help="weight in kilograms")
    parser.add_argument("height_m", type=float, help="height in metres")
    args = parser.parse_args()

    try:
        bmi = calculate_bmi(args.weight_kg, args.height_m)
    except ValueError as error:
        parser.error(str(error))

    print(f"BMI: {bmi:.2f} ({bmi_category(bmi)})")


if __name__ == "__main__":
    main()