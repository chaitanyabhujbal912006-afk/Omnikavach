import math

def detect_lab_anomalies(lab_values: list[float], threshold: float = 1.5) -> list[bool]:
    """
    The 'BS Detector': Catches dangerous lab spikes using Z-scores.
    Returns a list of booleans indicating if a value is a statistical outlier.
    """
    if len(lab_values) < 3:
        return [False] * len(lab_values) # Not enough data for statistics
    
    # Calculate Mean
    mean = sum(lab_values) / len(lab_values)
    
    # Calculate Standard Deviation
    variance = sum((x - mean) ** 2 for x in lab_values) / len(lab_values)
    std_dev = math.sqrt(variance)
    
    if std_dev == 0:
        return [False] * len(lab_values)
        
    # Calculate Z-Scores and flag anomalies
    z_scores = [(x - mean) / std_dev for x in lab_values]
    return [abs(z) > threshold for z in z_scores]

if __name__ == "__main__":
    # The last value (25.0) is a massive, dangerous spike
    test_wbc_labs = [12.0, 12.5, 12.1, 12.4, 25.0] 
    
    print(f"Lab Values: {test_wbc_labs}")
    print(f"Is Anomaly: {detect_lab_anomalies(test_wbc_labs)}")