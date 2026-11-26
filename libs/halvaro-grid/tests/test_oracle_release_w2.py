"""Release oracles of alarm_ticket_link, winter_peak_answer, interval_hours and sensor_quality_board. The expected values are computed another way than the functions: a dictionary of the stored link rows read one row at a time, strftime ISO week
labels with groupby on the stored daily table, division of the stored interval_s, and properties of the assembled answer (the pieces carried over, the label, the errors on a broken piece); small hand worked frames carry their numbers in the test."""
import numpy as np
import pandas as pd
import pytest

import halvaro.grid as grid
from halvaro.core import Context, FrameError

M12 = Context(stage="month12", role="r")


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# alarm_ticket_link
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------




def test_oracle_alarm_ticket_link_hand_worked_incident_tickets():
    """halvaro.grid.alarms.alarm_ticket_link: hand frame of five alarms of one element and type within 8 hours of each other (one incident) plus one of another element; two tickets are linked in the incident, the sixth alarm is alone and unlinked."""
    alarm = pd.DataFrame({"sns_key": ["S1", "S1", "S2", "S2", "S2", "S3"],
                          "raised_ts": pd.to_datetime(["2025-03-01 00:00", "2025-03-01 02:00", "2025-03-01 03:00", "2025-03-01 04:00", "2025-03-01 05:00", "2025-03-01 00:00"]),
                          "cleared_ts": pd.to_datetime(["2025-03-01 01:00", "2025-03-01 03:00", "2025-03-01 03:30", "2025-03-01 04:30", "2025-03-01 05:30", "2025-03-01 01:00"]),
                          "net_key": ["N1", "N1", "N1", "N1", "N1", "N2"], "alarm_type": ["a"] * 6}, index=[10, 11, 12, 13, 14, 15])
    ta = pd.DataFrame({"sns_key": ["S1", "S2"], "raised_ts": pd.to_datetime(["2025-03-01 00:00", "2025-03-01 04:00"]), "link_type": ["trigger", "precursor"], "tkt_key": ["T1", "T2"]})
    st = pd.DataFrame({"tkt_key": ["T1", "T2", "T3"]})
    out = grid.alarm_ticket_link(alarm, ta, st, context=M12)
    assert out.index.tolist() == [10, 11, 12, 13, 14, 15]
    assert out["linked"].tolist() == [True, False, False, True, False, False]
    assert [None if pd.isna(v) else v for v in out["tkt_key"]] == ["T1", None, None, "T2", None, None]
    assert [None if pd.isna(v) else v for v in out["link_type"]] == ["trigger", None, None, "precursor", None, None]
    assert out["incident_tickets"].tolist() == [2, 2, 2, 2, 2, 0], "five alarms of N1 run into one incident with two distinct tickets; N2 has none"
    assert out.loc[:4 + 10, "incident"].nunique() == 1 and out["incident"].iloc[5] != out["incident"].iloc[0]
    # without the incident columns the result has only the three link columns more
    slim = grid.alarm_ticket_link(alarm[["sns_key", "raised_ts"]], ta, st, context=M12)
    assert set(slim.columns) == {"sns_key", "raised_ts", "tkt_key", "link_type", "linked"}


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# interval_hours
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------



def test_oracle_interval_hours_hand_worked_and_errors():
    """halvaro.grid.series.interval_hours: hand worked intervals (900 s is a quarter, 1800 half, 3600 one, 7200 two hours, 60 s a sixtieth) and the three refusals."""
    s = pd.DataFrame({"sns_key": ["c", "a", "b", "d", "e"], "interval_s": [1800, 900, 3600, 7200, 60]}, index=[5, 6, 7, 8, 9])
    r = grid.interval_hours(s, context=M12)
    assert r.index.tolist() == ["c", "a", "b", "d", "e"]
    assert r.tolist() == [0.5, 0.25, 1.0, 2.0, 60 / 3600]
    for bad in (s.assign(interval_s=[1800, 0, 3600, 7200, 60]), s.assign(interval_s=[1800, -900, 3600, 7200, 60]), pd.concat([s, s.iloc[:1]]), s.drop(columns="interval_s")):
        with pytest.raises(FrameError):
            grid.interval_hours(bad, context=M12)


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# sensor_quality_board
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------

def test_oracle_sensor_quality_board_hand_worked_year_turn():
    """halvaro.grid.quality.sensor_quality_board: hand worked days around the turn of 2024/25 (2024-12-30 and 12-31 are in 2025-W01, 2025-01-08 in W02), a week without days and a second sensor, each weekly mean written down."""
    d = pd.DataFrame({"sns_key": ["A", "A", "A", "A", "B", "B"], "date": ["2024-12-30", "2024-12-31", "2025-01-08", "2025-01-21", "2025-01-01", "2025-01-21"],
                      "availability_pct": [100.0, 50.0, 80.0, 10.0, 33.333, 66.666]})
    b = grid.sensor_quality_board(d, context=M12)
    assert b.columns.tolist() == ["2025-W01", "2025-W02", "2025-W03", "2025-W04"]
    assert b.index.tolist() == ["A", "B"] and b.index.name == "sns_key"
    assert b.loc["A"].tolist()[:2] == [75.0, 80.0] and np.isnan(b.loc["A", "2025-W03"]) and b.loc["A", "2025-W04"] == 10.0
    assert b.loc["B", "2025-W01"] == 33.33 and b.loc["B", "2025-W04"] == 66.67 and b.loc["B", ["2025-W02", "2025-W03"]].isna().all()
    for bad in (d.drop(columns="date"), d.assign(availability_pct=[1.0, None, 1.0, 1.0, 1.0, 1.0]), pd.concat([d, d.iloc[:1]])):
        with pytest.raises(FrameError):
            grid.sensor_quality_board(bad, context=M12)



# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# winter_peak_answer
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
