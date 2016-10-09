# This repository is sperated into four parts:

## Data Preprocessing
### 
crawl ticker list and basic stock from http://www.nasdaq.com/screening/company-list.aspx

crawl financial report data from http://www.morningstar.com/

crawl historical stock prices from  https://finance.yahoo.com/

```python
./crawl.py
```

## Feature engineering

format basic information to the (sample_n, feature_m) matrix

[ feature1_sample_1, feature2_sample_1, ... feature_m_sample_1]

[ feature1_sample_2, feature2_sample_2, ... feature_m_sample_2]

[ feature1_sample_m, feature2_sample_m, ... feature_m_sample_n]

```python
./feature engineering.py
```

Basic feature filter to delete useless features


## Stock classification based on stock price
```python
./learning.py
```
## Optimize the best weight for your portfolio

```python
./mean_variance_optimization.py
```
