package main

import (
	"flag"
	"fmt"
)

func main() {

	/*var price float64
	var risk float64
	var stop float64
	var financeLevel float64
	var derivatePrice float64*/

	price := flag.Float64("price", 0, "Price of a stock")
	risk := flag.Float64("risk", 0, "Risk")
	stop := flag.Float64("stop", 0, "Stop")
	financeLevel := flag.Float64("financeLevel", 0, "Finance Level")
	derivatePrice := flag.Float64("derivatePrice", 0, "Derivate Price")

	flag.Parse()

	numberOfStocks := *risk / (*price - *stop)
	fmt.Printf("Stock> Number of stocks: %f\n", numberOfStocks)

	takeProfit := *price + 2*(*price-*stop)
	fmt.Printf("Stock> Take profit: %f\n", takeProfit)

	paritet := (*price - *financeLevel) / 100 * 8.34
	fmt.Printf("Mini> Leverage: %f\n", paritet)

	miniStop := (*stop - *financeLevel) / 100 * 8.34
	fmt.Printf("Mini> Stop: %f\n", miniStop)

	howMany := *risk / (*derivatePrice - miniStop)
	fmt.Printf("Mini> How many can I buy: %f\n", howMany)

	miniProfit := (((takeProfit - *financeLevel) / 100 * 8.34) * howMany) - (*derivatePrice * howMany)
	fmt.Printf("Mini> Profit: %f\n", miniProfit)
}
